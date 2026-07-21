"""Tests for multi-agent discussion orchestration (TD-02).

Covers:
- select_next_speaker: @mention, LLM output, round-robin fallback
- run_discussion_round: turn limit, speaker selection, convergence
- check_convergence: LLM output parsing, missing info tracking
- build_*_prompt: prompt generation
- build_discussion_agent_prompt: discussion mode constraints
"""

import asyncio
import sqlite3
from unittest.mock import MagicMock

import pytest

from app.core.database import Database
from app.orchestration.discussion import (
    MAX_AGENT_TURNS_PER_ROUND,
    TRANSCRIPT_WINDOW,
    DiscussionStatus,
    select_next_speaker,
    resolve_next_speaker,
    build_speaker_selection_prompt,
    run_discussion_round,
    build_discussion_context,
    check_convergence,
    build_convergence_prompt,
    build_brief_draft_prompt,
    build_discussion_agent_prompt,
    _extract_mention,
    _round_robin_pick,
    _format_transcript,
    _parse_speaker_json,
)


async def _drain(agen) -> list[dict]:
    """Collect all events from an async generator."""
    return [event async for event in agen]


def _run(agen) -> list[dict]:
    """Drive an async generator to completion synchronously."""
    return asyncio.run(_drain(agen))


def _run_coro(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


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
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT '',
            description TEXT
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


# --- Discussion round tests (TD-02-T2, async event stream via TD-02-T5) ---

class TestRunDiscussionRound:
    def test_no_message_from_executor_stops(self):
        db = _make_db()
        _insert_conversation(db)
        _insert_message(db, "conv_1", "user", "user_1", "开始讨论")

        async def noop(conn, agent_id):
            return
            yield  # pragma: no cover — makes this an async generator

        events = _run(
            run_discussion_round(
                db,
                workspace_id="ws_1",
                conversation_id="conv_1",
                member_agents=[{"id": "agent_abc"}],
                turn_executor=noop,
                debounce_seconds=0,
            )
        )
        end = events[-1]
        assert end["type"] == "end"
        assert end["turns_used"] == 0
        assert end["converged"] is False

    def test_respects_max_turns(self):
        db = _make_db()
        _insert_conversation(db)
        _insert_message(db, "conv_1", "user", "user_1", "开始讨论")

        call_count = 0

        async def reply(conn, agent_id):
            nonlocal call_count
            call_count += 1
            _insert_message(conn, "conv_1", "agent", agent_id, f"回复{call_count}", f"msg_{call_count}")
            yield {"type": "message", "message": {"id": f"msg_{call_count}"}}

        events = _run(
            run_discussion_round(
                db,
                workspace_id="ws_1",
                conversation_id="conv_1",
                member_agents=[{"id": "agent_abc"}],
                turn_executor=reply,
                max_turns=2,
                debounce_seconds=0,
            )
        )
        messages = [e for e in events if e["type"] == "message"]
        end = events[-1]
        assert len(messages) == 2
        assert end["turns_used"] == 2
        assert end["converged"] is True  # hit max_turns

    def test_emits_speaker_before_message(self):
        db = _make_db()
        _insert_conversation(db)
        _insert_message(db, "conv_1", "user", "user_1", "开始讨论")

        async def reply(conn, agent_id):
            _insert_message(conn, "conv_1", "agent", agent_id, "回复", "msg_1")
            yield {"type": "message", "message": {"id": "msg_1"}}

        events = _run(
            run_discussion_round(
                db,
                workspace_id="ws_1",
                conversation_id="conv_1",
                member_agents=[{"id": "agent_abc"}],
                turn_executor=reply,
                max_turns=1,
                debounce_seconds=0,
            )
        )
        types = [e["type"] for e in events]
        assert types[0] == "speaker"
        assert events[0]["agent_id"] == "agent_abc"
        assert "message" in types

    def test_stops_when_no_speaker(self):
        db = _make_db()
        _insert_conversation(db)
        _insert_message(db, "conv_1", "user", "user_1", "开始讨论")

        async def reply(conn, agent_id):
            yield {"type": "message", "message": {"id": "x"}}

        events = _run(
            run_discussion_round(
                db,
                workspace_id="ws_1",
                conversation_id="conv_1",
                member_agents=[],  # empty → no speaker
                turn_executor=reply,
                debounce_seconds=0,
            )
        )
        end = events[-1]
        assert end["turns_used"] == 0
        assert not any(e["type"] == "message" for e in events)

    def test_executor_exception_stops_round(self):
        db = _make_db()
        _insert_conversation(db)
        _insert_message(db, "conv_1", "user", "user_1", "开始讨论")

        async def failing(conn, agent_id):
            raise RuntimeError("LLM error")
            yield  # pragma: no cover — makes this an async generator

        events = _run(
            run_discussion_round(
                db,
                workspace_id="ws_1",
                conversation_id="conv_1",
                member_agents=[{"id": "agent_abc"}],
                turn_executor=failing,
                max_turns=4,
                debounce_seconds=0,
            )
        )
        errors = [e for e in events if e["type"] == "error"]
        end = events[-1]
        assert len(errors) == 1
        assert "LLM error" in errors[0]["detail"]
        assert isinstance(errors[0]["exc"], RuntimeError)
        assert end["turns_used"] == 0
        assert end["converged"] is False


# --- Full speaker resolution tests (TD-02-T5: LLM path moved into orchestration) ---

class TestResolveNextSpeaker:
    def test_mention_short_circuits_llm(self):
        db = _make_db()
        _insert_conversation(db)

        async def llm(prompt):  # pragma: no cover — must not be called
            raise AssertionError("LLM should not be called when @mention present")

        result = _run_coro(
            resolve_next_speaker(
                db,
                conversation_id="conv_1",
                member_agents=[{"id": "agent_abc", "name": "A", "role": "r", "description": ""}],
                last_message={"sender_type": "user", "content": "@agent_abc 上"},
                llm_complete=llm,
            )
        )
        assert result == "agent_abc"

    def test_llm_selects_speaker(self):
        db = _make_db()
        _insert_conversation(db)
        _insert_message(db, "conv_1", "user", "user_1", "大家讨论下")

        async def llm(prompt):
            return '{"next_speaker": "agent_def", "reason": "该他了"}'

        result = _run_coro(
            resolve_next_speaker(
                db,
                conversation_id="conv_1",
                member_agents=[
                    {"id": "agent_abc", "name": "A", "role": "r", "description": ""},
                    {"id": "agent_def", "name": "B", "role": "r", "description": ""},
                ],
                last_message={"sender_type": "user", "content": "大家讨论下"},
                llm_complete=llm,
            )
        )
        assert result == "agent_def"

    def test_llm_garbage_falls_back_to_round_robin(self):
        db = _make_db()
        _insert_conversation(db)
        _insert_message(db, "conv_1", "agent", "agent_abc", "我先说")

        async def llm(prompt):
            return "not json at all"

        result = _run_coro(
            resolve_next_speaker(
                db,
                conversation_id="conv_1",
                member_agents=[
                    {"id": "agent_abc", "name": "A", "role": "r", "description": ""},
                    {"id": "agent_def", "name": "B", "role": "r", "description": ""},
                ],
                last_message={"sender_type": "agent", "content": "我先说"},
                llm_complete=llm,
            )
        )
        # abc spoke last → round-robin picks def
        assert result == "agent_def"

    def test_no_llm_uses_round_robin(self):
        db = _make_db()
        _insert_conversation(db)

        result = _run_coro(
            resolve_next_speaker(
                db,
                conversation_id="conv_1",
                member_agents=[{"id": "agent_abc", "name": "A", "role": "r", "description": ""}],
                last_message=None,
                llm_complete=None,
            )
        )
        assert result == "agent_abc"

    def test_empty_members_returns_none(self):
        db = _make_db()
        _insert_conversation(db)

        result = _run_coro(
            resolve_next_speaker(
                db,
                conversation_id="conv_1",
                member_agents=[],
                last_message=None,
            )
        )
        assert result is None


class TestParseSpeakerJson:
    def test_valid_json(self):
        assert _parse_speaker_json('{"next_speaker": "a1"}') == {"next_speaker": "a1"}

    def test_json_embedded_in_text(self):
        assert _parse_speaker_json('好的 {"next_speaker": "a1"} 就这样') == {"next_speaker": "a1"}

    def test_no_json(self):
        assert _parse_speaker_json("随便说点什么") is None

    def test_empty(self):
        assert _parse_speaker_json("") is None


class TestBuildDiscussionContext:
    def test_includes_members_and_constraint(self):
        db = _make_db()
        _insert_conversation(db)
        _insert_message(db, "conv_1", "user", "u1", "开工")
        ctx = build_discussion_context(
            db,
            "conv_1",
            current_agent={"id": "a1", "name": "小明", "role": "设计师", "description": "画图"},
            all_agents=[
                {"id": "a1", "name": "小明", "role": "设计师", "description": "画图"},
                {"id": "a2", "name": "小红", "role": "工程师", "description": ""},
            ],
        )
        assert "群聊讨论模式" in ctx
        assert "小红" in ctx  # other member listed
        assert "小明" in ctx  # role constraint mentions the current agent
        assert "不允许宣称已执行" in ctx


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


# --- Convergence → brief_draft event tests (TD-02-T3 wired into production) ---

class TestDiscussionRoundConvergence:
    """讨论轮正常结束后（主持人 NONE 或达到轮数上限）且实际发言 ≥2 轮时，
    编排层用注入的主持人 LLM 回调做收敛检查：已对齐 → 产出 brief_draft 事件。
    编排层只产事件不写库（落库在路由层）。"""

    def _members(self):
        return [
            {"id": "agent_abc", "name": "分析师", "role": "分析", "description": ""},
            {"id": "agent_def", "name": "策划", "role": "策划", "description": ""},
        ]

    def _make_executor(self, state):
        async def reply(conn, agent_id):
            state["n"] += 1
            _insert_message(
                conn, "conv_1", "agent", agent_id,
                f"回复{state['n']}", f"msg_r{state['n']}",
            )
            yield {"type": "message", "message": {"id": f"msg_r{state['n']}"}}
        return reply

    def _make_llm(self, state, *, converged=True):
        """按 prompt 内容分发：选人 / 收敛判断 / 提炼 brief 各回各的。"""
        async def llm(prompt):
            if "选择下一个该发言的人" in prompt:
                state["speaker_calls"] += 1
                if state["speaker_calls"] <= 2:
                    nxt = self._members()[(state["speaker_calls"] - 1) % 2]["id"]
                    return f'{{"next_speaker": "{nxt}", "reason": "轮流"}}'
                return '{"next_speaker": "NONE", "reason": "讨论充分"}'
            if "判断讨论是否已经充分" in prompt:
                state["convergence_checks"] = state.get("convergence_checks", 0) + 1
                if converged:
                    return '{"converged": true, "missing": []}'
                return '{"converged": false, "missing": ["缺背景"]}'
            if "提炼共识纪要" in prompt:
                return (
                    '{"goal": "产出三篇选题", "scope": "小红书",'
                    ' "constraints": "周三前", "success_criteria": "定稿"}'
                )
            return "{}"
        return llm

    def test_brief_draft_emitted_when_converged(self):
        db = _make_db()
        _insert_conversation(db)
        _insert_message(db, "conv_1", "user", "user_1", "讨论下季度选题")
        state = {"n": 0, "speaker_calls": 0}

        events = _run(
            run_discussion_round(
                db,
                workspace_id="ws_1",
                conversation_id="conv_1",
                member_agents=self._members(),
                turn_executor=self._make_executor(state),
                llm_complete=self._make_llm(state, converged=True),
                debounce_seconds=0,
            )
        )
        brief_events = [e for e in events if e["type"] == "brief_draft"]
        assert len(brief_events) == 1
        draft = brief_events[0]["draft"]
        assert draft["goal"] == "产出三篇选题"
        assert draft["scope"] == "小红书"
        assert draft["constraints"] == "周三前"
        assert draft["success_criteria"] == "定稿"
        # brief_draft 必须在 end 之前，end 永远最后
        assert events[-1]["type"] == "end"
        assert events[-1]["turns_used"] == 2

    def test_no_brief_draft_when_not_converged(self):
        db = _make_db()
        _insert_conversation(db)
        _insert_message(db, "conv_1", "user", "user_1", "讨论下季度选题")
        state = {"n": 0, "speaker_calls": 0}

        events = _run(
            run_discussion_round(
                db,
                workspace_id="ws_1",
                conversation_id="conv_1",
                member_agents=self._members(),
                turn_executor=self._make_executor(state),
                llm_complete=self._make_llm(state, converged=False),
                debounce_seconds=0,
            )
        )
        assert not [e for e in events if e["type"] == "brief_draft"]
        # 收敛检查确实跑过（发言 ≥2 轮）
        assert state["convergence_checks"] == 1
        assert events[-1]["type"] == "end"

    def test_no_convergence_check_when_fewer_than_two_turns(self):
        """发言不足 2 轮的琐碎轮次不做收敛检查（省 LLM 调用）。"""
        db = _make_db()
        _insert_conversation(db)
        _insert_message(db, "conv_1", "user", "user_1", "随便聊一句")

        async def llm(prompt):
            if "选择下一个该发言的人" in prompt:
                # 只让一个人发言一次，随后主持人喊停
                if not hasattr(llm, "called"):
                    llm.called = True
                    return '{"next_speaker": "agent_abc", "reason": "他先说"}'
                return '{"next_speaker": "NONE", "reason": "够了"}'
            if "判断讨论是否已经充分" in prompt:
                raise AssertionError("发言不足 2 轮不应触发收敛检查")
            return "{}"

        state = {"n": 0}
        events = _run(
            run_discussion_round(
                db,
                workspace_id="ws_1",
                conversation_id="conv_1",
                member_agents=self._members(),
                turn_executor=self._make_executor(state),
                llm_complete=llm,
                debounce_seconds=0,
            )
        )
        assert events[-1]["type"] == "end"
        assert events[-1]["turns_used"] == 1
        assert not [e for e in events if e["type"] == "brief_draft"]

    def test_llm_failure_silently_yields_no_brief(self):
        """收敛检查 LLM 异常 / 返回垃圾 JSON → 静默不出 brief，讨论轮正常收尾。"""
        db = _make_db()
        _insert_conversation(db)
        _insert_message(db, "conv_1", "user", "user_1", "讨论下季度选题")
        state = {"n": 0, "speaker_calls": 0}

        async def llm(prompt):
            if "选择下一个该发言的人" in prompt:
                state["speaker_calls"] += 1
                if state["speaker_calls"] <= 2:
                    nxt = self._members()[(state["speaker_calls"] - 1) % 2]["id"]
                    return f'{{"next_speaker": "{nxt}", "reason": "轮流"}}'
                return '{"next_speaker": "NONE", "reason": "讨论充分"}'
            if "判断讨论是否已经充分" in prompt:
                raise RuntimeError("LLM 超时")
            return "{}"

        events = _run(
            run_discussion_round(
                db,
                workspace_id="ws_1",
                conversation_id="conv_1",
                member_agents=self._members(),
                turn_executor=self._make_executor(state),
                llm_complete=llm,
                debounce_seconds=0,
            )
        )
        assert not [e for e in events if e["type"] == "brief_draft"]
        assert events[-1]["type"] == "end"
        assert events[-1]["turns_used"] == 2
