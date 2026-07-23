"""Discussion orchestration for multi-agent group conversations.

Implements the AutoGen-inspired discussion skeleton:
1. Shared transcript (existing messages table)
2. Speaker selection (select_next_speaker)
3. Discussion round orchestration (run_discussion_round)
4. Convergence check + brief drafting (check_convergence)
5. Transition constraint: discussing state only allows discussion/question/brief

See ADR 0002, ADR 0006, and TD-02 for design details.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.core.database import Database
from app.core.logging import get_logger


logger = get_logger(__name__)

# Injected callbacks (provided by the route layer so orchestration never
# touches the runtime/HTTP layer directly — see services/api/AGENTS.md).
#
# TurnExecutor: given (conn, agent_id) produce this agent's reply. Yields
#   event dicts: {"type": "chunk", "content": str} for streaming, and finally
#   {"type": "message", "message": <row>} once persisted. Responsible for
#   committing so the next speaker selection can see the new message.
TurnExecutor = Callable[[Database, str], AsyncIterator[dict]]
# LlmComplete: given a system prompt, return the model's raw text completion.
LlmComplete = Callable[[str], Awaitable[str]]

# --- Configuration constants ---

MAX_AGENT_TURNS_PER_ROUND = 4
TRANSCRIPT_WINDOW = 30
MODERATOR_IS_DEFAULT_SECRETARY = True
# How long to wait, after a boss message arrives, before letting the group
# jump in — gives a quick burst of follow-up messages a chance to land first.
DISCUSSION_DEBOUNCE_SECONDS = 2.5
# 本轮实际发言轮数低于该值时不做收敛检查——一两句话的琐碎轮次不值得
# 花 LLM 调用判断"是否该产出共识 brief"。
MIN_TURNS_FOR_CONVERGENCE_CHECK = 2


class DiscussionStatus:
    """Discussion status constants."""

    DISCUSSING = "discussing"
    ALIGNED = "aligned"
    VALID_STATES = (DISCUSSING, ALIGNED)


def get_discussion_status(conn: Database, conversation_id: str) -> str:
    """Get the discussion status of a conversation."""
    row = conn.execute(
        "SELECT discussion_status FROM conversations WHERE id = ?",
        (conversation_id,),
    ).fetchone()
    if row is None:
        raise ValueError("conversation not found")
    return row["discussion_status"] or DiscussionStatus.DISCUSSING


def set_discussion_status(
    conn: Database,
    conversation_id: str,
    status: str,
) -> None:
    """Set the discussion status of a conversation."""
    if status not in DiscussionStatus.VALID_STATES:
        raise ValueError(f"Invalid discussion status: {status}")

    existing = conn.execute(
        "SELECT id FROM conversations WHERE id = ?",
        (conversation_id,),
    ).fetchone()
    if existing is None:
        raise ValueError("conversation not found")

    conn.execute(
        "UPDATE conversations SET discussion_status = ? WHERE id = ?",
        (status, conversation_id),
    )


# --- Speaker selection (TD-02-T1) ---

def select_next_speaker(
    conn: Database,
    conversation_id: str,
    member_agent_ids: list[str],
    last_message: dict | None = None,
    llm_output: dict[str, Any] | None = None,
) -> str | None:
    """Select the next speaker in a group discussion.

    Priority:
    1. If last message has @mention → select the mentioned agent
    2. If llm_output provided → use LLM's choice (with validation)
    3. Fallback: round-robin among members who haven't spoken recently

    Args:
        conn: Database connection
        conversation_id: Group conversation ID
        member_agent_ids: List of agent IDs in the group
        last_message: The last message dict (with 'sender_type', 'content', etc.)
        llm_output: Pre-parsed LLM output dict with 'next_speaker' and 'reason'.
            If None, uses round-robin fallback.

    Returns:
        Agent ID of next speaker, or None if discussion should pause.
    """
    if not member_agent_ids:
        return None

    # 1. Check for @mention in last message
    if last_message and last_message.get("content"):
        mentioned = _extract_mention(last_message["content"], member_agent_ids)
        if mentioned:
            return mentioned

    # 2. If LLM output provided, use it
    if llm_output:
        next_speaker = llm_output.get("next_speaker")
        if next_speaker and next_speaker in member_agent_ids:
            return next_speaker
        if next_speaker == "NONE":
            return None

    # 3. Fallback: round-robin — pick the member who spoke least recently
    recent_speakers = _get_recent_speakers(conn, conversation_id, limit=10)
    return _round_robin_pick(member_agent_ids, recent_speakers)


def build_speaker_selection_prompt(
    member_agents: list[dict],
    transcript: list[dict],
) -> str:
    """Build the system prompt for LLM speaker selection.

    Args:
        member_agents: List of agent dicts with 'id', 'name', 'role', 'description'
        transcript: Recent messages in the conversation

    Returns:
        System prompt string for LLM call
    """
    members_desc = "\n".join(
        f"- {a['id']}: {a['name']}（{a.get('role', '')}）— {a.get('description', '')}"
        for a in member_agents
    )
    transcript_text = _format_transcript(transcript)
    member_ids = ", ".join(a["id"] for a in member_agents)

    return f"""你是群讨论主持人，负责选择下一个该发言的人。

群成员：
{members_desc}

当前讨论记录：
{transcript_text}

请根据讨论进展，选择下一个最应该发言的人。以下情况都应返回 NONE（暂停，等老板回应），而不是换个人继续发言：
1. 讨论已足够充分，可以产出共识纪要。
2. 最近一条发言是在向老板提问 / 索要信息或决策（比如要链接、要素材、要拍板），且老板还没有回应——这种情况下让别的成员再问一遍同样的问题没有意义，应该停下来等老板回答，不要接力提问。
3. 最近几条发言已经在重复表达同一个意思（比如都在说"我打不开这个文件/权限不够"），继续发言只是重复噪音。

输出严格 JSON（不要多余文字）：
{{"next_speaker": "<agent_id>|NONE", "reason": "选择原因"}}

可选 next_speaker 值：{member_ids}，或 NONE"""


def _extract_mention(content: str, member_agent_ids: list[str]) -> str | None:
    """Extract @mentioned agent from message content.

    Supports @name format. Returns agent_id if found.
    """
    import re
    # Match @ followed by word chars (alphanumeric + underscore)
    # This avoids matching trailing punctuation as part of the name
    mentions = re.findall(r"@([\w]+)", content)
    if not mentions:
        return None

    for mention in mentions:
        if mention in member_agent_ids:
            return mention

    return None


def _get_recent_speakers(conn: Database, conversation_id: str, limit: int = 10) -> list[str]:
    """Get list of recent agent speaker IDs in the conversation."""
    rows = conn.execute(
        """SELECT sender_id FROM messages
        WHERE conversation_id = ? AND sender_type = 'agent'
        ORDER BY created_at DESC LIMIT ?""",
        (conversation_id, limit),
    ).fetchall()
    return [row["sender_id"] for row in rows]


def _round_robin_pick(
    member_agent_ids: list[str],
    recent_speakers: list[str],
) -> str | None:
    """Pick the member who spoke least recently (round-robin fallback)."""
    if not member_agent_ids:
        return None

    # Count recent appearances
    speak_count: dict[str, int] = {aid: 0 for aid in member_agent_ids}
    for speaker in recent_speakers:
        if speaker in speak_count:
            speak_count[speaker] += 1

    # Pick the one with fewest recent appearances
    min_count = min(speak_count.values())
    candidates = [aid for aid, count in speak_count.items() if count == min_count]
    return candidates[0]


# --- Full speaker resolution (mention → LLM → round-robin) ---

async def resolve_next_speaker(
    conn: Database,
    *,
    conversation_id: str,
    member_agents: list[Any],
    last_message: dict | None = None,
    llm_complete: LlmComplete | None = None,
) -> str | None:
    """Resolve the next speaker end-to-end.

    Priority: ① @mention in last message → ② moderator LLM (via injected
    ``llm_complete``) → ③ round-robin fallback. The @mention/validation/
    round-robin decisions live in :func:`select_next_speaker`; this wrapper
    only adds the LLM call (whose transport is injected so orchestration
    stays free of HTTP/runtime imports).
    """
    member_agent_ids = [a["id"] for a in member_agents]
    if not member_agent_ids:
        return None

    # @mention short-circuits before any LLM cost.
    if last_message and last_message.get("content"):
        mentioned = _extract_mention(last_message["content"], member_agent_ids)
        if mentioned:
            return mentioned

    llm_output: dict[str, Any] | None = None
    if llm_complete is not None:
        try:
            transcript = _load_transcript(conn, conversation_id)
            agent_dicts = [
                {
                    "id": a["id"],
                    "name": _row_get(a, "name"),
                    "role": _row_get(a, "role"),
                    "description": _row_get(a, "description"),
                }
                for a in member_agents
            ]
            prompt = build_speaker_selection_prompt(agent_dicts, transcript)
            text = await llm_complete(prompt)
            llm_output = _parse_speaker_json(text)
        except Exception:
            llm_output = None

    return select_next_speaker(
        conn,
        conversation_id=conversation_id,
        member_agent_ids=member_agent_ids,
        last_message=last_message,
        llm_output=llm_output,
    )


# --- Discussion round orchestration (TD-02-T2, wired via TD-02-T5) ---

async def run_discussion_round(
    conn: Database,
    *,
    workspace_id: str,
    conversation_id: str,
    member_agents: list[Any],
    turn_executor: TurnExecutor,
    llm_complete: LlmComplete | None = None,
    max_turns: int = MAX_AGENT_TURNS_PER_ROUND,
    debounce_seconds: float = DISCUSSION_DEBOUNCE_SECONDS,
) -> AsyncIterator[dict]:
    """Run one round of multi-agent discussion as an async event stream.

    This is the single production entry point for group discussion — both the
    streaming and non-streaming routes drive it. It owns the turn loop, speaker
    selection and convergence signalling; the route layer only injects how a
    turn is executed (``turn_executor``) and how the moderator LLM is called
    (``llm_complete``), and translates the yielded events to its transport
    (SSE frames for streaming, an accumulated list for non-streaming).

    Debounce: a human sending a quick burst of messages (elaborating a thought
    across several sends) shouldn't get the group jumping in after the first
    one. Before the round starts, wait ``debounce_seconds`` and re-check the
    latest message — if the boss sent something newer in the meantime, bail
    out silently; that follow-up message's own request will run the round
    (and sees the full transcript, so nothing is lost).

    After the turn loop ends (moderator returned NONE or max turns reached),
    a convergence check runs once the current round or shared transcript has
    at least ``MIN_TURNS_FOR_CONVERGENCE_CHECK`` agent turns:
    converged → a brief draft is produced and yielded as a ``brief_draft``
    event. The orchestration layer never writes the brief itself — the route
    layer consumes the event and persists it. Any failure in the check (LLM
    error, unparseable JSON) silently means "no brief this round".

    Yields event dicts:
      - {"type": "speaker", "agent_id": str}
      - {"type": "chunk", "content": str}          (re-emitted from turn_executor)
      - {"type": "message", "message": <row>}      (re-emitted from turn_executor)
      - {"type": "error", "detail": str, "exc": Exception}
      - {"type": "brief_draft", "draft": {goal, scope, constraints,
        success_criteria, owner_agent_id, work_items}}
      - {"type": "end", "converged": bool, "turns_used": int}   (always last)
    """
    turns_used = 0
    converged = False

    if debounce_seconds > 0:
        pre_debounce_message = _load_last_message(conn, conversation_id)
        await asyncio.sleep(debounce_seconds)
        latest_message = _load_last_message(conn, conversation_id)
        if latest_message != pre_debounce_message:
            yield {"type": "end", "converged": False, "turns_used": 0}
            return

    for _turn in range(max_turns):
        last_message = _load_last_message(conn, conversation_id)
        next_speaker = await resolve_next_speaker(
            conn,
            conversation_id=conversation_id,
            member_agents=member_agents,
            last_message=last_message,
            llm_complete=llm_complete,
        )
        if next_speaker is None:
            break

        yield {"type": "speaker", "agent_id": next_speaker}

        got_message = False
        try:
            async for event in turn_executor(conn, next_speaker):
                yield event
                if event.get("type") == "message":
                    got_message = True
        except Exception as exc:  # execution-layer failure → surface, stop round
            yield {"type": "error", "detail": str(exc), "exc": exc}
            break

        if not got_message:
            break

        turns_used += 1
        if turns_used >= max_turns:
            converged = True
            break

    # A multi-round discussion may already be aligned when the moderator picks
    # NONE. Count the shared transcript as well, otherwise "nothing left to add"
    # can never produce a brief.
    transcript_agent_turns = sum(
        1
        for message in _load_transcript(conn, conversation_id)
        if message.get("sender_type") == "agent"
    )
    should_check_convergence = (
        turns_used >= MIN_TURNS_FOR_CONVERGENCE_CHECK
        or transcript_agent_turns >= MIN_TURNS_FOR_CONVERGENCE_CHECK
    )
    if should_check_convergence and llm_complete is not None:
        draft = await _maybe_draft_brief(
            conn, conversation_id, llm_complete, member_agents=member_agents
        )
        if draft is not None:
            converged = True
            yield {"type": "brief_draft", "draft": draft}

    yield {"type": "end", "converged": converged, "turns_used": turns_used}


async def _maybe_draft_brief(
    conn: Database,
    conversation_id: str,
    llm_complete: LlmComplete,
    *,
    member_agents: list[Any],
) -> dict | None:
    """收敛检查 + brief 草稿生成（主持人 LLM 回调由路由层注入）。

    返回带完整 work_items 的草稿；未对齐或两次 JSON 校验均失败时
    环节失败（LLM 异常 / JSON 解析失败 / 缺 goal）都返回 None——绝不抛出，
    出不了 brief 不能影响正常发消息。
    """
    try:
        transcript = _load_transcript(conn, conversation_id)
        verdict_text = await llm_complete(build_convergence_prompt(transcript))
        verdict = check_convergence(
            conn, conversation_id, llm_output=_parse_speaker_json(verdict_text)
        )
        if not verdict["converged"]:
            return None

        row = conn.execute(
            "SELECT name FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        conversation_name = (row["name"] if row else "") or ""
        member_rows = [
            {
                "id": agent["id"],
                "name": _row_get(agent, "name"),
                "role": _row_get(agent, "role"),
                "description": _row_get(agent, "description"),
            }
            for agent in member_agents
        ]
        allowed_agent_ids = {row["id"] for row in member_rows}
        prompt = build_brief_draft_prompt(
            transcript, conversation_name, member_rows
        )
        draft_text = await llm_complete(prompt)
        for attempt in range(2):
            draft = _parse_speaker_json(draft_text)
            try:
                if not draft:
                    raise ValueError("response is not a JSON object")
                goal = draft.get("goal")
                if not isinstance(goal, str) or not goal.strip():
                    raise ValueError("goal is required")
                from app.orchestration.brief import validate_work_items

                work_items = validate_work_items(
                    draft.get("work_items") or [],
                    allowed_agent_ids=allowed_agent_ids,
                )
                owner_agent_id = str(draft.get("owner_agent_id") or "").strip()
                if owner_agent_id not in allowed_agent_ids:
                    owner_agent_id = next(
                        item["owner_agent_id"]
                        for item in work_items
                        if item["final_delivery"]
                    )
                return {
                    "goal": goal.strip()[:500],
                    "scope": str(draft.get("scope") or "")[:500],
                    "constraints": str(draft.get("constraints") or "")[:500],
                    "success_criteria": str(draft.get("success_criteria") or "")[:500],
                    "owner_agent_id": owner_agent_id,
                    "work_items": work_items,
                }
            except ValueError as exc:
                if attempt == 1:
                    logger.warning(
                        "brief_draft_validation_failed",
                        conversation_id=conversation_id,
                        error=str(exc),
                    )
                    return None
                draft_text = await llm_complete(
                    build_brief_repair_prompt(prompt, draft_text, str(exc))
                )
    except Exception as exc:
        logger.warning(
            "brief_draft_generation_failed",
            conversation_id=conversation_id,
            error=str(exc),
        )
        return None


# --- Convergence check (TD-02-T3) ---

def check_convergence(
    conn: Database,
    conversation_id: str,
    llm_output: dict[str, Any] | None = None,
) -> dict:
    """Check if the discussion has converged enough to draft a brief.

    Args:
        conn: Database connection
        conversation_id: Group conversation ID
        llm_output: Pre-parsed LLM output with 'converged' and 'missing'.
            If None, returns not converged.

    Returns:
        dict with keys:
        - converged: bool
        - missing: list[str] (what background is still missing)
    """
    if llm_output is None:
        return {"converged": False, "missing": ["LLM 未调用"]}

    converged = llm_output.get("converged", False)
    missing = llm_output.get("missing", [])

    if not isinstance(converged, bool):
        converged = False
    if not isinstance(missing, list):
        missing = []

    return {"converged": converged, "missing": missing}


def build_convergence_prompt(
    transcript: list[dict],
) -> str:
    """Build the system prompt for LLM convergence check.

    Args:
        transcript: Recent messages in the conversation

    Returns:
        System prompt string for LLM call
    """
    transcript_text = _format_transcript(transcript)

    return f"""你是群讨论主持人，负责判断讨论是否已经充分，可以产出共识纪要。

当前讨论记录：
{transcript_text}

判断标准：
1. 讨论的目标是否已经明确？
2. 平台、定位、受众、周期、数量、目标和约束是否已经明确？
3. 各成员的负责人、交付物和接力关系是否已经清晰？
4. 是否还有重要的背景信息缺失？

输出严格 JSON（不要多余文字）：
{{"converged": true/false, "missing": ["还缺什么背景1", "还缺什么背景2"]}}"""


def build_brief_draft_prompt(
    transcript: list[dict],
    conversation_name: str = "",
    members: list[dict] | None = None,
) -> str:
    """Build the system prompt for LLM brief drafting from discussion.

    Args:
        transcript: Recent messages
        conversation_name: Group conversation name

    Returns:
        System prompt string for LLM call
    """
    transcript_text = _format_transcript(transcript)
    member_text = "\n".join(
        f"- id={member['id']}，姓名={member.get('name', '')}，岗位={member.get('role', '')}，职责={member.get('description', '')}"
        for member in (members or [])
    ) or "- 无可分配成员"

    return f"""你是群讨论主持人，负责从讨论中提炼共识纪要。

群聊：{conversation_name or '群讨论'}
讨论记录：
{transcript_text}

可分配成员（owner_agent_id 必须原样使用这里的 id）：
{member_text}

根据讨论内容产出共识纪要草稿。必须拆成 3-6 个可执行 work item，依赖无环；
只能有一个 final_delivery=true 且 output_type=content_package_v1 的最终交付项。

输出严格 JSON（不要多余文字）：
{{
  "goal": "这次讨论要达成的目标（1-500字）",
  "scope": "范围和边界",
  "constraints": "约束条件",
  "success_criteria": "成功标准",
  "owner_agent_id": "总负责人 agent id",
  "work_items": [
    {{
      "key": "英文小写稳定键",
      "title": "任务标题",
      "description": "任务说明",
      "owner_agent_id": "成员 agent id",
      "expected_output": "预期交付物",
      "output_type": "markdown 或 content_package_v1",
      "depends_on_keys": ["前置任务 key"],
      "final_delivery": false
    }}
  ]
}}"""


def build_brief_repair_prompt(original_prompt: str, invalid_output: str, error: str) -> str:
    return f"""{original_prompt}

上一次输出没有通过校验：{error}
上一次输出：
{invalid_output[:8000]}

只返回修复后的完整 JSON，不要解释。"""


# --- Discussion prompt assembly ---

def build_discussion_agent_prompt(
    agent_name: str,
    agent_role: str,
    agent_description: str,
) -> str:
    """Build the additional system prompt for an agent in discussion mode.

    This is appended to the agent's normal prompt when in discussion state.
    """
    return f"""【讨论模式约束】
当前处于讨论阶段：只允许讨论/提问/补充背景，不允许宣称已执行任何动作。
你是 {agent_name}（{agent_role}），发言保持角色视角，不重复别人已说的。
如果背景不清楚，先在群里提问，不要臆测。
此时确认的是未来执行的负责人、依赖和预期交付契约；不要索要尚未执行产生的文件或结果。"""


# --- Discussion context assembly (per-agent prompt for a group turn) ---

def build_discussion_context(
    conn: Database,
    conversation_id: str,
    current_agent: Any,
    all_agents: list[Any],
) -> str:
    """Build the discussion-mode context string injected into an agent's turn.

    Includes: the other group members, the recent transcript, and the
    role-based discussion constraint. Kept in the orchestration layer so the
    route stays free of discussion business logic.
    """
    other_members = [
        f"- {a['name']}（{a['role']}）"
        for a in all_agents
        if a["id"] != current_agent["id"]
    ]
    members_str = "\n".join(other_members) if other_members else "无"

    transcript_rows = conn.execute(
        """SELECT messages.sender_type, messages.sender_id, messages.content,
                  agents.name AS agent_name
        FROM messages LEFT JOIN agents ON agents.id = messages.sender_id
        WHERE messages.conversation_id = ?
          AND messages.sender_type IN ('user', 'agent')
        ORDER BY messages.created_at DESC LIMIT 10""",
        (conversation_id,),
    ).fetchall()

    transcript_lines = []
    for row in reversed(transcript_rows):
        if row["sender_type"] == "user":
            name = "老板"
        else:
            name = _row_get(row, "agent_name") or row["sender_id"][:12]
        transcript_lines.append(f"{name}：{row['content'][:300]}")
    transcript_str = "\n".join(transcript_lines) if transcript_lines else "（暂无）"

    role_constraint = build_discussion_agent_prompt(
        agent_name=current_agent["name"],
        agent_role=current_agent["role"],
        agent_description=_row_get(current_agent, "description"),
    )

    return f"""【群聊讨论模式】
当前是群聊讨论，不是一对一私聊。你只是讨论的参与者之一，不是唯一回答者。

其他群成员：
{members_str}

最近讨论记录：
{transcript_str}

{role_constraint}

关键规则：
- 只从你的岗位角度出发，不要重复别人已经说过的内容
- 如果这个话题不涉及你的职责范围，可以简短表态或跳过
- 不要列出和前面的人一样的问题清单，而是在别人的基础上补充或推进
- 回复要简练，不要写长篇大论"""


# --- Helpers ---

def _row_get(row: Any, key: str, default: str = "") -> Any:
    """Safely read a column from a sqlite Row or a plain dict."""
    try:
        value = row[key]
    except (KeyError, IndexError):
        return default
    return value if value is not None else default


def _load_last_message(conn: Database, conversation_id: str) -> dict | None:
    row = conn.execute(
        """SELECT sender_type, sender_id, content FROM messages
        WHERE conversation_id = ? ORDER BY created_at DESC LIMIT 1""",
        (conversation_id,),
    ).fetchone()
    return dict(row) if row else None


def _load_transcript(
    conn: Database, conversation_id: str, limit: int = 20
) -> list[dict]:
    rows = conn.execute(
        """SELECT messages.sender_type, messages.sender_id, messages.content,
                  agents.name AS agent_name
        FROM messages LEFT JOIN agents ON agents.id = messages.sender_id
        WHERE messages.conversation_id = ?
          AND messages.sender_type IN ('user', 'agent')
        ORDER BY messages.created_at DESC LIMIT ?""",
        (conversation_id, limit),
    ).fetchall()
    return [dict(row) for row in reversed(rows)]


def _parse_speaker_json(text: str) -> dict | None:
    """Extract the moderator's speaker-selection JSON from raw LLM text.

    Returns the parsed dict (validated downstream by select_next_speaker) or
    None if no valid JSON object is present.
    """
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped)
    try:
        data = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        data = None
    if isinstance(data, dict):
        return data
    match = re.search(r"\{[^{}]*\}", text)
    if not match:
        return None
    try:
        data = json.loads(match.group())
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _format_transcript(transcript: list[dict]) -> str:
    """Format a list of message dicts into a readable transcript."""
    if not transcript:
        return "（暂无讨论记录）"

    lines = []
    for msg in transcript[-TRANSCRIPT_WINDOW:]:
        sender = msg.get("sender_type", "unknown")
        if sender == "user":
            name = "老板"
        elif sender == "agent":
            name = msg.get("sender_id", "agent")[:12]
        elif sender == "system":
            name = "系统"
        else:
            name = sender
        content = msg.get("content", "")[:500]
        lines.append(f"{name}：{content}")

    return "\n".join(lines)
