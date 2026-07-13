"""IdleThinkService (TD-08-T2) — idle employees proactively produce ideas.

North star §1.5: "no idle employees". When an employee has no work, it reflects
on recent work and drops ideas into the Idea center (TD-08-T1) instead of just
waiting.

A backend cron tick (wired in ``app.main``, off by default) scans for employees
that are ready, idle-thinking-enabled, due (last reflection older than their
per-employee interval), and have no active run. For each, we run a reflection
prompt through the employee's Hermes profile, parse the strict-JSON idea list it
returns, and write each idea into ``ideas``. The employee's ``last_idle_think_at``
is stamped afterwards regardless of outcome, so a failed/empty reflection does
not hot-loop.

Execution goes through the same ``RunBackend`` interface RunService uses
(``backend.run(ctx, permission_resolver=...)`` yielding ``AgentEvent``), so a
fake backend drives the always-on tests and real Hermes drives the guarded e2e.
Unlike a normal run, an idle reflection is not tied to a conversation and does
not create a ``runs`` row (``runs.conversation_id`` is NOT NULL); we drain the
event stream directly and only persist the resulting ideas.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.database import Database
from app.runtime.hermes_client import RunContext
from app.runtime.runs import RunStatus
from app.services.ideas import create_idea
from app.services.workspace import new_id, now_iso

_ACTIVE_RUN_STATUSES = (
    RunStatus.QUEUED,
    RunStatus.RUNNING,
    RunStatus.WAITING_USER,
    RunStatus.WAITING_CLARIFY,
)

_VALID_CATEGORIES = {"improvement", "opportunity", "risk", "learning"}
_MAX_IDEAS_PER_RUN = 3
_TITLE_MAX = 120
_DESC_MAX = 1000

IDLE_REFLECTION_PROMPT = (
    "你现在没有待处理的任务。请用下面的视角反思你最近的工作，产出对公司有价值的想法：\n"
    "1. improvement（改进）：最近工作中有没有可以做得更好的流程/方式？\n"
    "2. opportunity（机会）：你观察到什么值得尝试的方向或增长点？\n"
    "3. risk（风险）：有没有需要关注的潜在问题？\n"
    "4. learning（学习）：你学到了什么值得记录分享的经验？\n\n"
    "只输出严格 JSON 数组，不要任何解释文字或代码块标记：\n"
    '[{"title":"...","description":"...","category":"improvement|opportunity|risk|learning"}]\n'
    "每次 1-3 条，言简意赅、不要凑数；没有值得说的就输出 []。"
)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_ideas(text: str) -> list[dict]:
    """Extract and validate the strict-JSON idea list an employee returned.

    Tolerant of ```json fences and leading/trailing prose; keeps only well-formed
    items with a valid category, clamps lengths, and caps at ``_MAX_IDEAS_PER_RUN``.
    Returns ``[]`` on anything unparseable (never raises).
    """
    if not text:
        return []
    candidate = text.strip()
    # strip a ```json ... ``` fence if present
    fence = re.search(r"```(?:json)?\s*(.*?)```", candidate, re.DOTALL)
    if fence:
        candidate = fence.group(1).strip()
    # otherwise grab the first [...] array
    if not candidate.startswith("["):
        bracket = re.search(r"\[.*\]", candidate, re.DOTALL)
        if bracket:
            candidate = bracket.group(0)
    try:
        raw = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(raw, list):
        return []

    ideas: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        description = str(item.get("description", "")).strip()
        category = str(item.get("category", "")).strip().lower()
        if not title or not description or category not in _VALID_CATEGORIES:
            continue
        ideas.append(
            {
                "title": title[:_TITLE_MAX],
                "description": description[:_DESC_MAX],
                "category": category,
            }
        )
        if len(ideas) >= _MAX_IDEAS_PER_RUN:
            break
    return ideas


def find_due_idle_agents(
    conn: Database,
    *,
    now: datetime | None = None,
    workspace_id: str | None = None,
) -> list[dict]:
    """Employees eligible for an idle reflection right now.

    Eligible = spec ready + idle_thinking_enabled + has a Hermes profile + due
    (never reflected, or last reflection older than its interval) + no active run.
    """
    now = now or datetime.now(UTC)
    params: list[Any] = []
    where = [
        "s.status = 'ready'",
        "s.idle_thinking_enabled = 1",
        "s.hermes_profile IS NOT NULL",
        "s.hermes_profile != ''",
    ]
    if workspace_id:
        where.append("a.workspace_id = ?")
        params.append(workspace_id)
    rows = conn.execute(
        f"""
        SELECT a.id AS agent_id, a.workspace_id AS workspace_id,
               s.hermes_profile AS hermes_profile,
               s.last_idle_think_at AS last_idle_think_at,
               s.idle_think_interval_hours AS interval_hours
        FROM agent_specs s
        JOIN agents a ON a.id = s.agent_id
        WHERE {" AND ".join(where)}
        """,
        tuple(params),
    ).fetchall()

    due: list[dict] = []
    for row in rows:
        interval = row["interval_hours"] or 6
        last = _parse_dt(row["last_idle_think_at"])
        if last is not None and now - last < timedelta(hours=interval):
            continue
        active = conn.execute(
            "SELECT 1 FROM runs WHERE agent_id = ? AND status IN "
            f"({','.join('?' for _ in _ACTIVE_RUN_STATUSES)}) LIMIT 1",
            (row["agent_id"], *_ACTIVE_RUN_STATUSES),
        ).fetchone()
        if active:
            continue
        due.append(dict(row))
    return due


def _stamp_reflected(conn: Database, agent_id: str) -> None:
    conn.execute(
        "UPDATE agent_specs SET last_idle_think_at = ? WHERE agent_id = ?",
        (now_iso(), agent_id),
    )


async def trigger_reflection(
    conn: Database,
    *,
    agent_id: str,
    workspace_id: str,
    profile: str,
    backend: Any,
    hermes_work_root: str = "",
    timeout: int = 600,
) -> list[str]:
    """Run one idle reflection for an employee and persist the ideas it returns.

    Drains the backend, parses the JSON idea list, inserts each into ``ideas``,
    and stamps ``last_idle_think_at`` (even on empty/parse failure/backend error,
    so the cron does not immediately re-trigger). Returns the created idea ids.
    """
    work_root = os.path.abspath(hermes_work_root or ".hermes-data")
    ctx = RunContext(
        run_id="",
        prompt=IDLE_REFLECTION_PROMPT,
        workdir=os.path.join(work_root, profile, "work", "idle", new_id("idle")),
        profile=profile,
        agent_id=agent_id,
        workspace_id=workspace_id,
        timeout=timeout,
    )

    parts: list[str] = []
    try:
        async for event in backend.run(ctx, permission_resolver=None):
            if event.type == "message":
                content = event.payload.get("content") or {}
                if isinstance(content, dict):
                    parts.append(content.get("text", "") or "")
    except Exception:
        # transport/agent failure — stamp and move on, do not crash the tick
        _stamp_reflected(conn, agent_id)
        conn.commit()
        return []

    created: list[str] = []
    for idea in parse_ideas("".join(parts)):
        row = create_idea(
            conn,
            workspace_id=workspace_id,
            source_agent_id=agent_id,
            title=idea["title"],
            description=idea["description"],
            category=idea["category"],
        )
        created.append(row["id"])

    _stamp_reflected(conn, agent_id)
    conn.commit()
    return created


async def run_idle_tick(
    conn: Database,
    *,
    backend: Any,
    hermes_work_root: str = "",
    now: datetime | None = None,
    workspace_id: str | None = None,
) -> dict:
    """One cron pass: reflect for every due employee. Returns a summary."""
    due = find_due_idle_agents(conn, now=now, workspace_id=workspace_id)
    ideas_created = 0
    for agent in due:
        ids = await trigger_reflection(
            conn,
            agent_id=agent["agent_id"],
            workspace_id=agent["workspace_id"],
            profile=agent["hermes_profile"],
            backend=backend,
            hermes_work_root=hermes_work_root,
        )
        ideas_created += len(ids)
    return {"agents_processed": len(due), "ideas_created": ideas_created}
