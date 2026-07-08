"""Tests for multi-agent discussion orchestration (TD-02).

Covers:
- select_next_speaker: @mention, LLM output, round-robin fallback
- run_discussion_round: turn limit, speaker selection, convergence
- check_convergence: LLM output parsing, missing info tracking
- build_*_prompt: prompt generation
- build_discussion_agent_prompt: discussion mode constraints
"""

import sqlite3
from unittest.mock import MagicMock

import pytest

from app.core.database import Database
from app.orchestration.discussion import (
    MAX_AGENT_TURNS_PER_ROUND,
    TRANSCRIPT_WINDOW,
    DiscussionStatus,
    select_next_speaker,
    build_speaker_selection_prompt,
    run_discussion_round,
    check_convergence,
    build_convergence_prompt,
    build_brief_draft_prompt,
    build_discussion_agent_prompt,
    _extract_mention,
    _round_robin_pick,
    _format_transcript,
)


def _make_db() -> Database:
    """Create an in-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db = Database(conn, "sqlite")
    # Minimal schema for discussion tests
    db.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'group',
            name TEXT NOT NULL DEFAULT '',
            agent_id TEXT,
            unread INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            discussion_status TEXT NOT NULL DEFAULT 'discussing'
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            sender_type TEXT NOT NULL,
            sender_id TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL,
            provider TEXT,
            model TEXT,
            created_at TEXT NOT NULL
        );
    """)
    return db


def _insert_conversation(db: Database, conv_id: str = "conv_1") -> None:
    db.execute(
        """INSERT INTO conversations (id, workspace_id, kind, name, created_at, updated_at)
        VALUES (?, 'ws_1', 'group', '测试群', '2026-01-01T00:00:00', '2026-01-01T00:00:00')""",
        (conv_id,),
    )


def _insert_message(db: Database, conv_id: str, sender_type: str, sender_id: str, content: str, msg_id: str | None = None) -> None:
    db.execute(
        """INSERT INTO messages (id, conversation_id, sender_type, sender_id, content, created_at)
        VALUES (?, ?, ?, ?, ?, '2026-01-01T00:00:00')""",
        (msg_id or f"msg_{sender_type}_{sender_id[:8]}", conv_id, sender_type, sender_id, content),
    )


# --- Speaker selection tests (TD-02-T1) ---

class TestSelectNextSpeaker:
    def test_mention_selects_mentioned_agent(self):
        db = _make_db()
        _insert_conversation(db)
        _insert_message(db, "conv_1", "user", "user_1", "@agent_abc 你觉得呢？")

        result = select_next_speaker(
            db,
            conversation_id="conv_1",
            member_agent_ids=["agent_abc", "agent_def"],
            last_message={"sender_type": "user", "content": "@agent_abc 你觉得呢？"},
        )
        assert result == "agent_abc"

    def test_no_mention_no_llm_falls_to_round_robin(self):
        db = _make_db()
        _insert_conversation(db)
        # agent_abc spoke recently, agent_def didn't
        _insert_message(db, "conv_1", "agent", "agent_abc", "我说完了")

        result = select_next_speaker(
            db,
            conversation_id="conv_1",
            member_agent_ids=["agent_abc", "agent_def"],
            last_message={"sender_type": "agent", "content": "我说完了"},
        )
        assert result == "agent_def"

    def test_llm_selects_valid_speaker(self):
        db = _make_db()
        _insert_conversation(db)

        result = select_next_speaker(
            db,
            conversation_id="conv_1",
            member_agent_ids=["agent_abc", "agent_def"],
            llm_output={"next_speaker": "agent_def", "reason": "该他发言了"},
        )
        assert result == "agent_def"

    def test_llm_selects_none_stops_discussion(self):
        db = _make_db()
        _insert_conversation(db)

        result = select_next_speaker(
            db,
            conversation_id="conv_1",
            member_agent_ids=["agent_abc", "agent_def"],
            llm_output={"next_speaker": "NONE", "reason": "讨论已充分"},
        )
        assert result is None

    def test_llm_invalid_speaker_falls_to_round_robin(self):
        db = _make_db()
        _insert_conversation(db)

        result = select_next_speaker(
            db,
            conversation_id="conv_1",
            member_agent_ids=["agent_abc", "agent_def"],
            llm_output={"next_speaker": "nonexistent_agent", "reason": "错误"},
        )
        # Should fall back to round-robin, returning one of the members
        assert result in ["agent_abc", "agent_def"]

    def test_empty_members_returns_none(self):
        db = _make_db()
        _insert_conversation(db)

        result = select_next_speaker(
            db,
            conversation_id="conv_1",
            member_agent_ids=[],
        )
        assert result is None

    def test_mention_priority_over_llm(self):
        """@mention should take priority over LLM suggestion."""
        db = _make_db()
        _insert_conversation(db)

        result = select_next_speaker(
            db,
            conversation_id="conv_1",
            member_agent_ids=["agent_abc", "agent_def"],
            last_message={"sender_type": "user", "content": "@agent_abc 回答一下"},
            llm_output={"next_speaker": "agent_def", "reason": "LLM建议"},
        )
        assert result == "agent_abc"


class TestExtractMention:
    def test_basic_mention(self):
        assert _extract_mention("@agent_abc 你好", ["agent_abc", "agent_def"]) == "agent_abc"

    def test_no_mention(self):
        assert _extract_mention("大家好", ["agent_abc"]) is None

    def test_mention_with_punctuation(self):
        assert _extract_mention("@agent_abc，你觉得呢？", ["agent_abc"]) == "agent_abc"

    def test_mention_not_in_members(self):
        assert _extract_mention("@someone_else", ["agent_abc"]) is None


class TestRoundRobinPick:
    def test_picks_least_recent(self):
        recent = ["a", "a", "b"]
        assert _round_robin_pick(["a", "b", "c"], recent) == "c"

    def test_all_equal_picks_first(self):
        assert _round_robin_pick(["a", "b"], []) == "a"

    def test_empty_members(self):
        assert _round_robin_pick([], []) is None


# --- Discussion round tests (TD-02-T2) ---

class TestRunDiscussionRound:
    def test_dry_run_no_callback(self):
        db = _make_db()
        _insert_conversation(db)
        _insert_message(db, "conv_1", "user", "user_1", "开始讨论")

        result = run_discussion_round(
            db,
            workspace_id="ws_1",
            conversation_id="conv_1",
            member_agent_ids=["agent_abc"],
            on_agent_reply=None,  # dry run
        )
        assert result["turns_used"] == 0
        assert result["agent_messages"] == []
        assert result["converged"] is False

    def test_with_callback_respects_max_turns(self):
        db = _make_db()
        _insert_conversation(db)
        _insert_message(db, "conv_1", "user", "user_1", "开始讨论")

        call_count = 0

        def mock_reply(conn, agent_id, conversation_id):
            nonlocal call_count
            call_count += 1
            _insert_message(conn, conversation_id, "agent", agent_id, f"回复{call_count}", f"msg_{call_count}")
            return {"id": f"msg_{call_count}", "content": f"回复{call_count}"}

        result = run_discussion_round(
            db,
            workspace_id="ws_1",
            conversation_id="conv_1",
            member_agent_ids=["agent_abc"],
            max_turns=2,
            on_agent_reply=mock_reply,
        )
        assert result["turns_used"] == 2
        assert result["converged"] is True  # hit max_turns

    def test_stops_when_no_speaker(self):
        db = _make_db()
        _insert_conversation(db)
        _insert_message(db, "conv_1", "user", "user_1", "开始讨论")

        result = run_discussion_round(
            db,
            workspace_id="ws_1",
            conversation_id="conv_1",
            member_agent_ids=[],  # empty → no speaker
            on_agent_reply=lambda *a: None,
        )
        assert result["turns_used"] == 0

    def test_callback_exception_stops_round(self):
        db = _make_db()
        _insert_conversation(db)
        _insert_message(db, "conv_1", "user", "user_1", "开始讨论")

        def failing_reply(conn, agent_id, conversation_id):
            raise RuntimeError("LLM error")

        result = run_discussion_round(
            db,
            workspace_id="ws_1",
            conversation_id="conv_1",
            member_agent_ids=["agent_abc"],
            max_turns=4,
            on_agent_reply=failing_reply,
        )
        assert result["turns_used"] == 0
        assert result["converged"] is False


# --- Convergence tests (TD-02-T3) ---

class TestCheckConvergence:
    def test_no_llm_output_returns_not_converged(self):
        db = _make_db()
        result = check_convergence(db, "conv_1")
        assert result["converged"] is False
        assert len(result["missing"]) > 0

    def test_converged_true(self):
        db = _make_db()
        result = check_convergence(db, "conv_1", llm_output={"converged": True, "missing": []})
        assert result["converged"] is True
        assert result["missing"] == []

    def test_not_converged_with_missing(self):
        db = _make_db()
        result = check_convergence(db, "conv_1", llm_output={"converged": False, "missing": ["缺少用户画像"]})
        assert result["converged"] is False
        assert "缺少用户画像" in result["missing"]

    def test_invalid_converged_field(self):
        db = _make_db()
        result = check_convergence(db, "conv_1", llm_output={"converged": "yes", "missing": []})
        assert result["converged"] is False


# --- Prompt building tests ---

class TestBuildSpeakerSelectionPrompt:
    def test_contains_member_info(self):
        agents = [
            {"id": "agent_1", "name": "前端工程师", "role": "工程师", "description": "写代码"},
            {"id": "agent_2", "name": "设计师", "role": "设计", "description": "画图"},
        ]
        prompt = build_speaker_selection_prompt(agents, [])
        assert "前端工程师" in prompt
        assert "设计师" in prompt
        assert "agent_1" in prompt
        assert "agent_2" in prompt

    def test_contains_transcript(self):
        transcript = [{"sender_type": "user", "content": "开始讨论"}]
        prompt = build_speaker_selection_prompt([], transcript)
        assert "开始讨论" in prompt


class TestBuildConvergencePrompt:
    def test_contains_transcript(self):
        transcript = [{"sender_type": "agent", "sender_id": "a1", "content": "我认为应该这样做"}]
        prompt = build_convergence_prompt(transcript)
        assert "我认为应该这样做" in prompt
        assert "converged" in prompt.lower() or "收敛" in prompt


class TestBuildBriefDraftPrompt:
    def test_contains_conversation_name(self):
        prompt = build_brief_draft_prompt([], "产品讨论群")
        assert "产品讨论群" in prompt

    def test_contains_goal_field(self):
        prompt = build_brief_draft_prompt([], "")
        assert "goal" in prompt


class TestBuildDiscussionAgentPrompt:
    def test_contains_agent_info(self):
        prompt = build_discussion_agent_prompt("小明", "设计师", "画图")
        assert "小明" in prompt
        assert "设计师" in prompt

    def test_contains_discussion_constraint(self):
        prompt = build_discussion_agent_prompt("小明", "设计师", "画图")
        assert "讨论" in prompt
        assert "不允许宣称已执行" in prompt


class TestFormatTranscript:
    def test_empty_transcript(self):
        assert "暂无" in _format_transcript([])

    def test_formats_user_message(self):
        result = _format_transcript([{"sender_type": "user", "content": "你好"}])
        assert "老板" in result
        assert "你好" in result

    def test_formats_agent_message(self):
        result = _format_transcript([{"sender_type": "agent", "sender_id": "agent_abc123", "content": "收到"}])
        assert "agent_abc1" in result
        assert "收到" in result

    def test_truncates_long_content(self):
        long_content = "x" * 600
        result = _format_transcript([{"sender_type": "user", "content": long_content}])
        assert len(result) < 600
