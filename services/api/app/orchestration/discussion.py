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

import json
from typing import Any

from app.core.database import Database

# --- Configuration constants ---

MAX_AGENT_TURNS_PER_ROUND = 4
TRANSCRIPT_WINDOW = 30
MODERATOR_IS_DEFAULT_SECRETARY = True


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

请根据讨论进展，选择下一个最应该发言的人。如果讨论已足够充分可以产出共识纪要，返回 NONE。

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


# --- Discussion round orchestration (TD-02-T2) ---

def run_discussion_round(
    conn: Database,
    *,
    workspace_id: str,
    conversation_id: str,
    member_agent_ids: list[str],
    max_turns: int = MAX_AGENT_TURNS_PER_ROUND,
    on_agent_reply: Any | None = None,
) -> dict:
    """Run one round of multi-agent discussion.

    This is called from the route layer when a group conversation is in
    'discussing' state. It orchestrates multiple agent turns in sequence.

    Args:
        conn: Database connection
        workspace_id: Workspace ID
        conversation_id: Group conversation ID
        member_agent_ids: List of agent IDs in the group
        max_turns: Maximum consecutive agent turns before pausing
        on_agent_reply: Async callback(conn, agent_id, conversation_id) -> message_row
            If None, no actual LLM calls are made (dry run for testing).

    Returns:
        dict with keys:
        - agent_messages: list of agent message rows
        - converged: bool (whether check_convergence says to stop)
        - turns_used: int (number of agent turns used)
    """
    agent_messages = []
    converged = False

    for turn in range(max_turns):
        # Select next speaker
        last_msg_row = conn.execute(
            """SELECT sender_type, sender_id, content FROM messages
            WHERE conversation_id = ? ORDER BY created_at DESC LIMIT 1""",
            (conversation_id,),
        ).fetchone()
        last_message = dict(last_msg_row) if last_msg_row else None

        next_speaker = select_next_speaker(
            conn,
            conversation_id=conversation_id,
            member_agent_ids=member_agent_ids,
            last_message=last_message,
        )

        if next_speaker is None:
            break

        # Call the agent reply callback
        if on_agent_reply is not None:
            try:
                msg = on_agent_reply(conn, next_speaker, conversation_id)
                if msg is not None:
                    agent_messages.append(msg)
            except Exception:
                break
        else:
            # Dry run — no actual LLM call
            break

        # Check convergence after each agent turn
        # (simplified: not calling LLM here, just check turn count)
        if turn + 1 >= max_turns:
            converged = True
            break

    return {
        "agent_messages": agent_messages,
        "converged": converged,
        "turns_used": len(agent_messages),
    }


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
2. 各成员的分工是否已经清晰？
3. 是否还有重要的背景信息缺失？

输出严格 JSON（不要多余文字）：
{{"converged": true/false, "missing": ["还缺什么背景1", "还缺什么背景2"]}}"""


def build_brief_draft_prompt(
    transcript: list[dict],
    conversation_name: str = "",
) -> str:
    """Build the system prompt for LLM brief drafting from discussion.

    Args:
        transcript: Recent messages
        conversation_name: Group conversation name

    Returns:
        System prompt string for LLM call
    """
    transcript_text = _format_transcript(transcript)

    return f"""你是群讨论主持人，负责从讨论中提炼共识纪要。

群聊：{conversation_name or '群讨论'}
讨论记录：
{transcript_text}

根据讨论内容，产出共识纪要草稿。

输出严格 JSON（不要多余文字）：
{{
  "goal": "这次讨论要达成的目标（1-500字）",
  "scope": "范围和边界",
  "constraints": "约束条件",
  "success_criteria": "成功标准"
}}"""


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
如果背景不清楚，先在群里提问，不要臆测。"""


# --- Helpers ---

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
