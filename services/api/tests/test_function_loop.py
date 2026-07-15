"""Tests for Agent Action Bridge — function-calling loop that lets agents
actually operate the system (create employees, tasks, groups, etc.).

Tests use a fake DeepSeek client that returns pre-crafted tool_call responses,
so the tests are fast and deterministic.
"""

import asyncio
import json
import sqlite3

import pytest

from app.core.database import Database, connect
from app.schemas.run import LlmChatMessage
from app.tools.registry import (
    execute_tool,
    system_prompt_for_operator,
)
from app.tools.function_loop import (
    _extract_tool_calls,
    _extract_text,
    ToolCall,
)


# ---------------------------------------------------------------------------
# Fake DeepSeek client for testing the function loop
# ---------------------------------------------------------------------------

class FakeDeepSeek:
    """A fake DeepSeek client that returns pre-programmed responses."""

    api_key = "fake"
    base_url = "https://fake/"
    model = "deepseek-v4-flash"
    timeout_seconds = 30

    def __init__(self, responses: list[dict]):
        """responses: list of raw API response dicts to return in order."""
        self.responses = responses
        self.call_count = 0

    async def post(self, *args, **kwargs):
        pass  # Not used in tests


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_tool_call_extraction():
    msg = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "create_employee",
                    "arguments": '{"name": "小明", "role": "程序员", "description": "写代码"}',
                },
            }
        ],
    }
    calls = _extract_tool_calls(msg)
    assert len(calls) == 1
    assert calls[0].name == "create_employee"
    assert calls[0].arguments["name"] == "小明"


def test_tool_call_no_tools_returns_text():
    msg = {"role": "assistant", "content": "你好老板"}
    calls = _extract_tool_calls(msg)
    assert calls == []
    assert _extract_text(msg) == "你好老板"


def test_system_prompt_includes_workspace():
    prompt = system_prompt_for_operator("测试公司", "小秘", "万能助手")
    assert "测试公司" in prompt
    assert "小秘" in prompt
    assert "创建新员工" in prompt
    assert "no_action_needed" in prompt


# ---------------------------------------------------------------------------
# Integration tests — actual tool execution against in-memory SQLite
# ---------------------------------------------------------------------------

def _make_db() -> Database:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db = Database(conn, "sqlite")
    db.executescript("""
        CREATE TABLE workspaces (
            id TEXT PRIMARY KEY, owner_user_id TEXT NOT NULL, name TEXT NOT NULL,
            onboarding_completed INTEGER DEFAULT 0, created_at TEXT NOT NULL
        );
        CREATE TABLE departments (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, name TEXT NOT NULL,
            parent_id TEXT, sort_order INTEGER DEFAULT 0, created_at TEXT NOT NULL
        );
        CREATE TABLE agents (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, department_id TEXT NOT NULL,
            name TEXT NOT NULL, role TEXT NOT NULL, description TEXT DEFAULT '',
            prompt TEXT NOT NULL, hue INTEGER DEFAULT 220, glyph TEXT DEFAULT '◆',
            status_kind TEXT DEFAULT 'idle', status_label TEXT DEFAULT '在线待命',
            joined TEXT DEFAULT '今天入职', source TEXT DEFAULT 'custom',
            skills_json TEXT DEFAULT '[]', mcps_json TEXT DEFAULT '[]',
            created_at TEXT NOT NULL, updated_at TEXT DEFAULT ''
        );
        CREATE TABLE conversations (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, kind TEXT DEFAULT 'group',
            name TEXT DEFAULT '', agent_id TEXT, unread INTEGER DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT DEFAULT ''
        );
        CREATE TABLE conversation_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,
            agent_id TEXT NOT NULL
        );
        CREATE TABLE messages (
            id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, sender_type TEXT NOT NULL,
            sender_id TEXT DEFAULT '', content TEXT NOT NULL,
            provider TEXT, model TEXT, created_at TEXT NOT NULL, external_message_id TEXT
        );
        INSERT INTO workspaces (id, owner_user_id, name, created_at)
        VALUES ('ws_test', 'user_1', '测试公司', '2026-01-01T00:00:00');
        INSERT INTO departments (id, workspace_id, name, created_at)
        VALUES ('dept_1', 'ws_test', '技术部', '2026-01-01T00:00:00');
        INSERT INTO agents (id, workspace_id, department_id, name, role, prompt, created_at)
        VALUES ('agent_1', 'ws_test', 'dept_1', '小秘', '万能助手', '你是小秘', '2026-01-01T00:00:00');
    """)
    return db


def test_execute_create_employee():
    """Test that create_employee tool actually creates an agent in the DB."""
    db = _make_db()
    agent = dict(db.execute("SELECT * FROM agents WHERE id = 'agent_1'").fetchone())

    tc = ToolCall(
        id="call_test",
        name="create_employee",
        arguments={"name": "工程师小王", "role": "后端工程师", "description": "负责后端开发", "department": "技术部"},
    )

    result = asyncio.run(execute_tool(db, "ws_test", agent, tc))
    data = json.loads(result.content)
    assert data["success"] is True
    assert data["agent"]["name"] == "工程师小王"
    assert data["agent"]["role"] == "后端工程师"

    # Verify the agent exists in the DB
    new_agent = db.execute(
        "SELECT * FROM agents WHERE name = '工程师小王'"
    ).fetchone()
    assert new_agent is not None
    assert new_agent["role"] == "后端工程师"


def test_execute_create_group():
    """Test that create_group creates a group conversation."""
    db = _make_db()
    agent = dict(db.execute("SELECT * FROM agents WHERE id = 'agent_1'").fetchone())

    # First create another agent to be a member
    db.execute(
        "INSERT INTO agents (id, workspace_id, department_id, name, role, prompt, created_at) "
        "VALUES ('agent_2', 'ws_test', 'dept_1', '小明', '设计师', '你是设计师', '2026-01-01T00:00:00')"
    )

    tc = ToolCall(
        id="call_grp",
        name="create_group",
        arguments={"name": "测试群", "member_agent_ids": ["agent_1", "agent_2"]},
    )

    result = asyncio.run(execute_tool(db, "ws_test", agent, tc))
    data = json.loads(result.content)
    assert data["success"] is True
    assert data["group"]["name"] == "测试群"
    assert data["group"]["member_count"] == 2


def test_execute_list_agents():
    """Test that list_agents returns the workspace's agents."""
    db = _make_db()
    agent = dict(db.execute("SELECT * FROM agents WHERE id = 'agent_1'").fetchone())

    tc = ToolCall(id="call_list", name="list_agents", arguments={})
    result = asyncio.run(execute_tool(db, "ws_test", agent, tc))
    data = json.loads(result.content)
    assert data["total"] >= 1
    names = [a["name"] for a in data["agents"]]
    assert "小秘" in names


def test_execute_create_task():
    """Test that create_task creates a task in the DB."""
    db = _make_db()
    # Need the tasks table
    db.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, conversation_id TEXT,
            parent_task_id TEXT, consensus_brief_id TEXT,
            title TEXT NOT NULL, description TEXT DEFAULT '',
            priority TEXT DEFAULT 'P2', status TEXT DEFAULT '待认领',
            progress INTEGER DEFAULT 0, owner_agent_id TEXT, due_date TEXT,
            created_at TEXT NOT NULL, updated_at TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS task_events (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, task_id TEXT NOT NULL,
            kind TEXT NOT NULL, title TEXT DEFAULT '', content TEXT DEFAULT '',
            conversation_id TEXT, agent_id TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS task_outputs (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, task_id TEXT NOT NULL,
            title TEXT DEFAULT '', content TEXT DEFAULT '',
            conversation_id TEXT, agent_id TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
            sender_type TEXT NOT NULL, sender_id TEXT DEFAULT '',
            content TEXT NOT NULL, provider TEXT, model TEXT,
            created_at TEXT NOT NULL, external_message_id TEXT
        );
    """)
    agent = dict(db.execute("SELECT * FROM agents WHERE id = 'agent_1'").fetchone())

    tc = ToolCall(
        id="call_task",
        name="create_task",
        arguments={
            "title": "搭建用户系统",
            "description": "实现注册登录功能",
            "priority": "P1",
            "owner_agent_id": "agent_1",
        },
    )

    result = asyncio.run(execute_tool(db, "ws_test", agent, tc))
    data = json.loads(result.content)
    assert data["success"] is True
    assert data["task"]["title"] == "搭建用户系统"

    # Verify in DB
    task = db.execute("SELECT * FROM tasks WHERE title = '搭建用户系统'").fetchone()
    assert task is not None
    assert task["priority"] == "P1"


def test_execute_unknown_tool_returns_error():
    """Unknown tool should return an error, not crash."""
    db = _make_db()
    agent = dict(db.execute("SELECT * FROM agents WHERE id = 'agent_1'").fetchone())

    tc = ToolCall(id="call_bad", name="nonexistent_tool", arguments={})
    result = asyncio.run(execute_tool(db, "ws_test", agent, tc))
    data = json.loads(result.content)
    assert "error" in data


def test_execute_no_action():
    """no_action_needed should work without side effects."""
    db = _make_db()
    agent = dict(db.execute("SELECT * FROM agents WHERE id = 'agent_1'").fetchone())

    tc = ToolCall(id="call_noop", name="no_action_needed", arguments={})
    result = asyncio.run(execute_tool(db, "ws_test", agent, tc))
    data = json.loads(result.content)
    assert data["action"] == "none"


def test_execute_add_group_member():
    """add_group_member should add an agent to an existing group."""
    db = _make_db()
    # Create a group and another agent
    db.executescript("""
        INSERT INTO agents (id, workspace_id, department_id, name, role, prompt, created_at)
        VALUES ('agent_3', 'ws_test', 'dept_1', '小李', '运营', '你是运营', '2026-01-01T00:00:00');
        INSERT INTO conversations (id, workspace_id, kind, name, created_at, updated_at)
        VALUES ('conv_grp', 'ws_test', 'group', '项目群', '2026-01-01T00:00:00', '2026-01-01T00:00:00');
        INSERT INTO conversation_members (conversation_id, agent_id) VALUES ('conv_grp', 'agent_1');
    """)
    agent = dict(db.execute("SELECT * FROM agents WHERE id = 'agent_1'").fetchone())

    tc = ToolCall(
        id="call_add",
        name="add_group_member",
        arguments={"conversation_id": "conv_grp", "agent_ids": ["agent_3"]},
    )

    result = asyncio.run(execute_tool(db, "ws_test", agent, tc))
    data = json.loads(result.content)
    assert data["success"] is True
    assert data["added"] == 1

    # Verify member was added
    members = db.execute(
        "SELECT agent_id FROM conversation_members WHERE conversation_id = 'conv_grp'"
    ).fetchall()
    member_ids = [m["agent_id"] for m in members]
    assert "agent_3" in member_ids


def test_execute_create_task_missing_title():
    """create_task without title should return error."""
    db = _make_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
            title TEXT NOT NULL, description TEXT DEFAULT '',
            priority TEXT DEFAULT 'P2', status TEXT DEFAULT '待认领',
            progress INTEGER DEFAULT 0, owner_agent_id TEXT, conversation_id TEXT,
            due_date TEXT, parent_task_id TEXT, consensus_brief_id TEXT,
            created_at TEXT NOT NULL, updated_at TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS task_events (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, task_id TEXT NOT NULL,
            kind TEXT NOT NULL, title TEXT DEFAULT '', content TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS task_outputs (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, task_id TEXT NOT NULL,
            title TEXT DEFAULT '', content TEXT DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
            sender_type TEXT NOT NULL, sender_id TEXT DEFAULT '',
            content TEXT NOT NULL, provider TEXT, model TEXT,
            created_at TEXT NOT NULL, external_message_id TEXT
        );
    """)
    agent = dict(db.execute("SELECT * FROM agents WHERE id = 'agent_1'").fetchone())

    tc = ToolCall(id="call_bad", name="create_task", arguments={"description": "no title"})
    result = asyncio.run(execute_tool(db, "ws_test", agent, tc))
    data = json.loads(result.content)
    assert "error" in data
    assert "标题" in data["error"]


def test_execute_create_employee_without_name():
    """create_employee without name should return error."""
    db = _make_db()
    agent = dict(db.execute("SELECT * FROM agents WHERE id = 'agent_1'").fetchone())

    tc = ToolCall(
        id="call_bad", name="create_employee",
        arguments={"role": "工程师", "description": "no name"},
    )
    result = asyncio.run(execute_tool(db, "ws_test", agent, tc))
    data = json.loads(result.content)
    assert "error" in data
    assert "名字" in data["error"]
