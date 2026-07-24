"""ReflectionService (TD-06-T1) — employees sediment experience into skills.

North star §1.4: an employee gets *better at this company* the more it works —
not by swapping in a smarter model, but by distilling each batch of runs into
reusable SKILL.md fragments stored in its own Hermes profile.

Flow: every ``reflection_interval`` completed runs (counter bumped by RunService),
a background tick (or ``POST /api/agents/{id}/reflect``) summarizes the employee's
recent ``run_steps``, asks the employee (through its own Hermes profile) to distill
1–3 reusable work lessons as strict JSON, and writes each into the profile via
``ProfileProvisioner.update_skill``. The counter resets and ``last_skill_reflection_at``
is stamped.

Execution goes through the same ``RunBackend`` interface RunService/IdleThink use
(``backend.run(ctx)`` yielding ``AgentEvent``), so a fake backend drives tests and
real Hermes drives the guarded e2e. Like idle reflection, this is not tied to a
conversation and creates no ``runs`` row.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from app.core.database import Database
from app.runtime.hermes_client import RunContext
from app.runtime.runs import RunStatus
from app.services.workspace import new_id, now_iso

_MAX_SKILLS_PER_RUN = 3
_NAME_MAX = 80
_CONTENT_MAX = 2000
_DEFAULT_RUN_WINDOW = 5

REFLECTION_PROMPT_HEAD = (
    "你刚完成了下面这些工作。请从中提炼 1-3 条**可复用**的工作经验（怎么做得更好、"
    "有效的工具调用顺序、这家公司/客户的偏好、踩过的坑），写成可以下次直接照做的技能片段。\n\n"
    "只输出严格 JSON 数组，不要任何解释或代码块标记：\n"
    '[{"skill_name":"简短技能名","content":"# 技能名\\n\\n何时用：...\\n步骤/要点：..."}]\n'
    "每条 content 用 Markdown，言简意赅、可操作；没有值得沉淀的就输出 []。\n\n"
    "=== 最近的工作流水 ===\n"
)


def _summarize_recent_steps(
    conn: Database, agent_id: str, *, run_window: int = _DEFAULT_RUN_WINDOW
) -> str:
    """Compact text of the agent's most recent runs' steps (for the prompt)."""
    runs = conn.execute(
        """
        SELECT id FROM runs
        WHERE agent_id = ? AND status = ?
        ORDER BY created_at DESC LIMIT ?
        """,
        (agent_id, RunStatus.COMPLETED, run_window),
    ).fetchall()
    if not runs:
        return ""
    run_ids = [r["id"] for r in runs]
    placeholders = ",".join("?" for _ in run_ids)
    steps = conn.execute(
        f"""
        SELECT run_id, type, title, detail FROM run_steps
        WHERE run_id IN ({placeholders})
          AND type IN ('message','tool_call','tool_result','final')
        ORDER BY created_at ASC
        """,
        tuple(run_ids),
    ).fetchall()
    lines: list[str] = []
    for step in steps:
        label = step["title"] or step["type"]
        body = (step["detail"] or "").strip().replace("\n", " ")
        if body:
            lines.append(f"- [{step['type']}] {label}: {body[:300]}")
        elif step["type"] != "final":
            lines.append(f"- [{step['type']}] {label}")
    return "\n".join(lines[:60])


def parse_skills(text: str) -> list[dict]:
    """Extract + validate the strict-JSON skill list. Never raises; ``[]`` on junk."""
    if not text:
        return []
    candidate = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", candidate, re.DOTALL)
    if fence:
        candidate = fence.group(1).strip()
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

    skills: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("skill_name", "")).strip()
        content = str(item.get("content", "")).strip()
        if not name or not content:
            continue
        skills.append({"skill_name": name[:_NAME_MAX], "content": content[:_CONTENT_MAX]})
        if len(skills) >= _MAX_SKILLS_PER_RUN:
            break
    return skills


def bump_reflection_counter(conn: Database, agent_id: str) -> bool:
    """Increment runs_since_last_reflection; return True when the interval is hit.

    No-op (returns False) for agents without a spec. Caller commits.
    """
    spec = conn.execute(
        "SELECT runs_since_last_reflection, reflection_interval "
        "FROM agent_specs WHERE agent_id = ?",
        (agent_id,),
    ).fetchone()
    if spec is None:
        return False
    count = (spec["runs_since_last_reflection"] or 0) + 1
    conn.execute(
        "UPDATE agent_specs SET runs_since_last_reflection = ? WHERE agent_id = ?",
        (count, agent_id),
    )
    return count >= (spec["reflection_interval"] or _DEFAULT_RUN_WINDOW)


def find_agents_due_for_reflection(
    conn: Database, *, workspace_id: str | None = None
) -> list[dict]:
    """Ready employees whose completed-run counter has reached their interval."""
    params: list[Any] = []
    where = [
        "s.status = 'ready'",
        "s.hermes_profile IS NOT NULL",
        "s.hermes_profile != ''",
        "s.runs_since_last_reflection >= s.reflection_interval",
    ]
    if workspace_id:
        where.append("a.workspace_id = ?")
        params.append(workspace_id)
    rows = conn.execute(
        f"""
        SELECT a.id AS agent_id, a.workspace_id AS workspace_id,
               s.hermes_profile AS hermes_profile
        FROM agent_specs s JOIN agents a ON a.id = s.agent_id
        WHERE {" AND ".join(where)}
        """,
        tuple(params),
    ).fetchall()
    return [dict(r) for r in rows]


async def run_reflection(
    conn: Database,
    *,
    agent_id: str,
    backend: Any,
    provisioner: Any,
    hermes_work_root: str = "",
    run_window: int = _DEFAULT_RUN_WINDOW,
) -> list[str]:
    """Distill the agent's recent runs into skills, persist them, reset the counter.

    Returns the skill names written. Resets ``runs_since_last_reflection`` and
    stamps ``last_skill_reflection_at`` regardless of outcome (even on empty
    output / backend error) so it does not re-trigger immediately.
    """
    spec = conn.execute(
        "SELECT workspace_id, hermes_profile FROM agent_specs WHERE agent_id = ?",
        (agent_id,),
    ).fetchone()
    if spec is None or not spec["hermes_profile"]:
        return []
    profile = spec["hermes_profile"]
    workspace_id = spec["workspace_id"]

    summary = _summarize_recent_steps(conn, agent_id, run_window=run_window)

    written: list[str] = []
    if summary:  # nothing to reflect on if there are no steps yet
        work_root = os.path.abspath(hermes_work_root or ".hermes-data")
        ctx = RunContext(
            run_id="",
            prompt=REFLECTION_PROMPT_HEAD + summary,
            workdir=os.path.join(
                work_root, profile, "work", "reflect", new_id("reflect")
            ),
            profile=profile,
            agent_id=agent_id,
            workspace_id=workspace_id,
        )
        from app.services.model_credentials import (
            ModelCredentialRequired,
            runtime_model_environment,
        )

        parts: list[str] = []
        try:
            ctx.environment.update(runtime_model_environment(conn, workspace_id))
        except ModelCredentialRequired:
            pass
        else:
            try:
                async for event in backend.run(ctx, permission_resolver=None):
                    if event.type == "message":
                        content = event.payload.get("content") or {}
                        if isinstance(content, dict):
                            parts.append(content.get("text", "") or "")
            except Exception:
                parts = []  # fall through to stamp + return

        for skill in parse_skills("".join(parts)):
            provisioner.update_skill(profile, skill["skill_name"], skill["content"])
            written.append(skill["skill_name"])

    conn.execute(
        "UPDATE agent_specs SET runs_since_last_reflection = 0, "
        "last_skill_reflection_at = ? WHERE agent_id = ?",
        (now_iso(), agent_id),
    )
    conn.commit()
    return written


async def run_reflection_tick(
    conn: Database,
    *,
    backend: Any,
    provisioner: Any,
    hermes_work_root: str = "",
    workspace_id: str | None = None,
) -> dict:
    """One background pass: reflect for every employee that has hit its interval."""
    due = find_agents_due_for_reflection(conn, workspace_id=workspace_id)
    skills_learned = 0
    for agent in due:
        names = await run_reflection(
            conn,
            agent_id=agent["agent_id"],
            backend=backend,
            provisioner=provisioner,
            hermes_work_root=hermes_work_root,
        )
        skills_learned += len(names)
    return {"agents_reflected": len(due), "skills_learned": skills_learned}
