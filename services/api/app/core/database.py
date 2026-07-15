from __future__ import annotations

from collections.abc import Generator, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import re
import sqlite3

import psycopg
import psycopg_pool
from psycopg.rows import dict_row

from app.core.config import settings
from app.services.templates import seed_official_talent_market


Params = Sequence[Any]


class Row(dict):
    """Tiny dict row that keeps sqlite-style key access for service code."""


class Result:
    def __init__(self, rows: list[Row] | None = None):
        self._rows = rows or []

    def fetchone(self) -> Row | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[Row]:
        return self._rows

# ---------------------------------------------------------------------------
# Placeholder translation — replaces `?` with the dialect-native placeholder
# but *not* inside single-quoted strings (avoids breaking string literals
# that happen to contain a literal ? character).
# ---------------------------------------------------------------------------

def _translate_placeholders(sql: str, dialect: str) -> str:
    """Replace ``?`` placeholders with dialect-native markers.

    Skips ``?`` inside single-quoted SQL string literals (e.g. ``'what?'``).
    """
    if dialect == "sqlite":
        return sql
    # PostgreSQL uses %s
    result: list[str] = []
    in_string = False
    for ch in sql:
        if ch == "'":
            in_string = not in_string
            result.append(ch)
        elif ch == "?" and not in_string:
            result.append("%s")
        else:
            result.append(ch)
    return "".join(result)




class Database:
    def __init__(self, conn: Any, dialect: str):
        self.conn = conn
        self.dialect = dialect

    def execute(self, sql: str, params: Params = ()) -> Result:
        if self.dialect == "postgres":
            return self._execute_postgres(sql, params)
        return self._execute_sqlite(sql, params)

    def executescript(self, script: str) -> None:
        if self.dialect == "postgres":
            for statement in split_sql_script(script):
                self.execute(statement)
            return
        self.conn.executescript(script)

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

    def close(self) -> None:
        self.conn.close()

    def _execute_postgres(self, sql: str, params: Params) -> Result:
        translated_sql = _translate_placeholders(sql, "postgres")
        with self.conn.cursor() as cursor:
            cursor.execute(translated_sql, tuple(params))
            if cursor.description is None:
                return Result()
            return Result([Row(row) for row in cursor.fetchall()])

    def _execute_sqlite(self, sql: str, params: Params) -> Result:
        cursor = self.conn.execute(sql, tuple(params))
        if cursor.description is None:
            return Result()
        return Result([Row(dict(row)) for row in cursor.fetchall()])

# ---------------------------------------------------------------------------
# Connection pooling
# ---------------------------------------------------------------------------

_pg_pool: "psycopg_pool.ConnectionPool | None" = None


def _pg_pool_instance() -> "psycopg_pool.ConnectionPool":
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = psycopg_pool.ConnectionPool(
            settings.database_url,
            kwargs={"row_factory": dict_row},
            min_size=1,
            max_size=10,
            open=True,
        )
    return _pg_pool




def connect() -> Database:
    database_url = settings.database_url
    if is_sqlite_url(database_url):
        return connect_sqlite(database_url)
    pool = _pg_pool_instance()
    conn = pool.getconn()
    return Database(conn, "postgres")


def connect_sqlite(database_url: str) -> Database:
    path = sqlite_path(database_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return Database(conn, "sqlite")


def sqlite_path(database_url: str) -> Path:
    raw_path = database_url.removeprefix("sqlite:///")
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def is_sqlite_url(database_url: str) -> bool:
    return database_url.startswith("sqlite:///")


def get_db() -> Generator[Database, None, None]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
        # Return the connection to the pool (no-op for SQLite)
        if _pg_pool is not None and hasattr(conn, "conn"):
            _pg_pool.putconn(conn.conn)  # type: ignore[arg-type]

def shutdown_db() -> None:
    """Close the PostgreSQL pool gracefully (call on app shutdown)."""
    global _pg_pool
    if _pg_pool is not None:
        _pg_pool.close()
        _pg_pool = None




def init_db() -> None:
    conn = connect()
    try:
        if conn.dialect == "postgres":
            init_postgres(conn)
        else:
            init_sqlite(conn)
        seed_official_talent_market(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_postgres(conn: Database) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
          id TEXT PRIMARY KEY,
          email TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL,
          display_name TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS official_talent_categories (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          sort_order INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'published',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS official_agent_templates (
          id TEXT PRIMARY KEY,
          category_id TEXT NOT NULL REFERENCES official_talent_categories(id) ON DELETE RESTRICT,
          name TEXT NOT NULL,
          department TEXT NOT NULL DEFAULT '',
          description TEXT NOT NULL DEFAULT '',
          prompt TEXT NOT NULL,
          skills_json TEXT NOT NULL DEFAULT '[]',
          mcps_json TEXT NOT NULL DEFAULT '[]',
          publisher TEXT NOT NULL DEFAULT 'AgentPulse 官方',
          version TEXT NOT NULL DEFAULT 'v0.1.0',
          status TEXT NOT NULL DEFAULT 'published',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS workspaces (
          id TEXT PRIMARY KEY,
          owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          name TEXT NOT NULL,
          onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS departments (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          name TEXT NOT NULL,
          sort_order INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          UNIQUE(workspace_id, name)
        );

        CREATE TABLE IF NOT EXISTS agents (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          department_id TEXT NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
          name TEXT NOT NULL,
          role TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          prompt TEXT NOT NULL,
          hue INTEGER NOT NULL DEFAULT 220,
          glyph TEXT NOT NULL DEFAULT '◆',
          status_kind TEXT NOT NULL DEFAULT 'idle',
          status_label TEXT NOT NULL DEFAULT '在线待命',
          joined TEXT NOT NULL DEFAULT '今天入职',
          source TEXT NOT NULL DEFAULT 'custom',
          skills_json TEXT NOT NULL DEFAULT '[]',
          mcps_json TEXT NOT NULL DEFAULT '[]',
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conversations (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          kind TEXT NOT NULL CHECK(kind IN ('dm', 'group')),
          name TEXT NOT NULL DEFAULT '',
          agent_id TEXT REFERENCES agents(id) ON DELETE CASCADE,
          unread INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conversation_members (
          id BIGSERIAL PRIMARY KEY,
          conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
          UNIQUE(conversation_id, agent_id)
        );

        CREATE TABLE IF NOT EXISTS messages (
          id TEXT PRIMARY KEY,
          conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          sender_type TEXT NOT NULL CHECK(sender_type IN ('user', 'agent', 'system')),
          sender_id TEXT NOT NULL DEFAULT '',
          content TEXT NOT NULL,
          provider TEXT,
          model TEXT,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          title TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          priority TEXT NOT NULL DEFAULT 'P2',
          owner_agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
          status TEXT NOT NULL DEFAULT '进行中',
          progress INTEGER NOT NULL DEFAULT 0,
          conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
          due_date TEXT,
          parent_task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS knowledge_sources (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          title TEXT NOT NULL,
          category TEXT NOT NULL DEFAULT '通用资料',
          content TEXT NOT NULL,
          created_by TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS task_events (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
          conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
          agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
          kind TEXT NOT NULL,
          title TEXT NOT NULL,
          content TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS task_outputs (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
          conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
          agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
          title TEXT NOT NULL,
          output_type TEXT NOT NULL DEFAULT 'markdown',
          content TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS approvals (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
          task_id TEXT REFERENCES tasks(id) ON DELETE CASCADE,
          conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
          agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
          title TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'pending',
          risk_level TEXT NOT NULL DEFAULT 'medium',
          type TEXT NOT NULL DEFAULT 'high_risk'
            CHECK(type IN ('high_risk','clarification','capability_upgrade')),
          payload_json TEXT NOT NULL DEFAULT '{}',
          resolved_by TEXT NOT NULL DEFAULT '',
          resolved_at TEXT,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_experiences (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
          task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
          outcome TEXT NOT NULL,
          summary TEXT NOT NULL,
          lessons TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS consensus_briefs (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          discussion_conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'confirmed', 'rejected', 'superseded')),
          goal TEXT NOT NULL,
          scope TEXT NOT NULL DEFAULT '',
          constraints TEXT NOT NULL DEFAULT '',
          success_criteria TEXT NOT NULL DEFAULT '',
          owner_agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
          participant_agent_ids_json TEXT NOT NULL DEFAULT '[]',
          created_by_agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
          supersedes_brief_id TEXT REFERENCES consensus_briefs(id) ON DELETE SET NULL,
          derived_from_brief_id TEXT REFERENCES consensus_briefs(id) ON DELETE SET NULL,
          created_at TEXT NOT NULL,
          confirmed_at TEXT,
          confirmed_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS runs (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
          task_id TEXT REFERENCES tasks(id) ON DELETE CASCADE,
          status TEXT NOT NULL,
          input_message_id TEXT NOT NULL,
          output_message_id TEXT,
          hermes_profile_id TEXT,
          hermes_run_id TEXT,
          workdir TEXT,
          provider TEXT NOT NULL DEFAULT 'deepseek',
          model TEXT NOT NULL DEFAULT '',
          usage_json TEXT NOT NULL DEFAULT '{}',
          error TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS run_steps (
          id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
          type TEXT NOT NULL CHECK(type IN (
            'message','thinking','tool_call','tool_result',
            'approval_required','status','final'
          )),
          status TEXT NOT NULL DEFAULT '',
          title TEXT NOT NULL DEFAULT '',
          detail TEXT NOT NULL DEFAULT '',
          payload_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ideas (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          source_agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
          title TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          category TEXT NOT NULL CHECK(category IN (
            'improvement','opportunity','risk','learning'
          )),
          status TEXT NOT NULL DEFAULT 'new' CHECK(status IN (
            'new','reviewed','accepted','dismissed','converted'
          )),
          converted_brief_id TEXT REFERENCES consensus_briefs(id) ON DELETE SET NULL,
          created_at TEXT NOT NULL,
          reviewed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS channel_configs (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          channel_type TEXT NOT NULL CHECK(channel_type IN (
            'wechat','email','web_widget','generic_webhook'
          )),
          name TEXT NOT NULL,
          token TEXT NOT NULL UNIQUE,
          config_json TEXT NOT NULL DEFAULT '{}',
          target_agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
          target_conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_specs (
          id TEXT PRIMARY KEY,
          agent_id TEXT NOT NULL UNIQUE REFERENCES agents(id) ON DELETE CASCADE,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          role_name TEXT NOT NULL,
          source_request TEXT NOT NULL DEFAULT '',
          responsibilities_json TEXT NOT NULL DEFAULT '[]',
          hermes_profile TEXT,
          status TEXT NOT NULL DEFAULT 'draft'
            CHECK(status IN ('draft','provisioning','blocked_on_credentials','ready','failed')),
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_capabilities (
          id TEXT PRIMARY KEY,
          agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          capability_key TEXT NOT NULL,
          skill_refs_json TEXT NOT NULL DEFAULT '[]',
          toolset_refs_json TEXT NOT NULL DEFAULT '[]',
          mcp_refs_json TEXT NOT NULL DEFAULT '[]',
          required_credentials_json TEXT NOT NULL DEFAULT '[]',
          risk_gate TEXT NOT NULL DEFAULT 'auto'
            CHECK(risk_gate IN ('auto','approval','prohibited_auto')),
          status TEXT NOT NULL DEFAULT 'pending'
            CHECK(status IN ('pending','credential_missing','enabled','disabled')),
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(agent_id, capability_key)
        );
        """
    )
    ensure_column(conn, "messages", "provider", "TEXT")
    ensure_column(conn, "messages", "model", "TEXT")
    ensure_column(conn, "tasks", "description", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "tasks", "due_date", "TEXT")
    ensure_column(conn, "tasks", "parent_task_id", "TEXT REFERENCES tasks(id) ON DELETE SET NULL")
    ensure_column(conn, "tasks", "consensus_brief_id", "TEXT REFERENCES consensus_briefs(id) ON DELETE SET NULL")
    ensure_column(conn, "conversations", "discussion_status", "TEXT NOT NULL DEFAULT 'discussing' CHECK(discussion_status IN ('discussing', 'aligned'))")
    # TD-03-T1: Run/RunStep data model. New columns are nullable here; RunService
    # (TD-03-T3) enforces "every Run belongs to a Task" + absolute workdir at the
    # application layer once execution actually flows through Hermes.
    ensure_column(conn, "runs", "task_id", "TEXT REFERENCES tasks(id) ON DELETE CASCADE")
    ensure_column(conn, "runs", "hermes_profile_id", "TEXT")
    ensure_column(conn, "runs", "hermes_run_id", "TEXT")
    ensure_column(conn, "runs", "workdir", "TEXT")
    ensure_column(conn, "approvals", "run_id", "TEXT REFERENCES runs(id) ON DELETE SET NULL")
    ensure_column(
        conn,
        "approvals",
        "type",
        "TEXT NOT NULL DEFAULT 'high_risk' "
        "CHECK(type IN ('high_risk','clarification','capability_upgrade'))",
    )
    ensure_column(
        conn, "approvals", "payload_json", "TEXT NOT NULL DEFAULT '{}'"
    )
    ensure_column(conn, "agents", "hermes_gateway_port", "INTEGER")
    # TD-08-T1: idea center (idle reflection). idle_thinking_enabled stored as
    # 0/1 INTEGER in both dialects (serialized to bool at the API layer).
    ensure_column(conn, "agent_specs", "last_idle_think_at", "TEXT")
    ensure_column(
        conn, "agent_specs", "idle_think_interval_hours", "INTEGER NOT NULL DEFAULT 6"
    )
    ensure_column(
        conn, "agent_specs", "idle_thinking_enabled", "INTEGER NOT NULL DEFAULT 1"
    )
    # TD-06-T1: skill self-sedimentation (reflection cron).
    ensure_column(
        conn, "agent_specs", "runs_since_last_reflection", "INTEGER NOT NULL DEFAULT 0"
    )
    ensure_column(conn, "agent_specs", "last_skill_reflection_at", "TEXT")
    ensure_column(
        conn, "agent_specs", "reflection_interval", "INTEGER NOT NULL DEFAULT 5"
    )
    ensure_column(
        conn, "conversations", "idea_id", "TEXT REFERENCES ideas(id) ON DELETE SET NULL"
    )
    # TD-09-T1: external channel adapters. Conversations remember which channel
    # (and external thread) they came from; messages carry the external id for
    # webhook-redelivery dedup.
    ensure_column(conn, "conversations", "source_channel", "TEXT")
    ensure_column(conn, "conversations", "external_conversation_id", "TEXT")
    ensure_column(conn, "messages", "external_message_id", "TEXT")


def init_sqlite(conn: Database) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
          id TEXT PRIMARY KEY,
          email TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL,
          display_name TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS official_talent_categories (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          sort_order INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'published',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS official_agent_templates (
          id TEXT PRIMARY KEY,
          category_id TEXT NOT NULL REFERENCES official_talent_categories(id) ON DELETE RESTRICT,
          name TEXT NOT NULL,
          department TEXT NOT NULL DEFAULT '',
          description TEXT NOT NULL DEFAULT '',
          prompt TEXT NOT NULL,
          skills_json TEXT NOT NULL DEFAULT '[]',
          mcps_json TEXT NOT NULL DEFAULT '[]',
          publisher TEXT NOT NULL DEFAULT 'AgentPulse 官方',
          version TEXT NOT NULL DEFAULT 'v0.1.0',
          status TEXT NOT NULL DEFAULT 'published',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS workspaces (
          id TEXT PRIMARY KEY,
          owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          name TEXT NOT NULL,
          onboarding_completed INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS departments (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          name TEXT NOT NULL,
          sort_order INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          UNIQUE(workspace_id, name)
        );

        CREATE TABLE IF NOT EXISTS agents (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          department_id TEXT NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
          name TEXT NOT NULL,
          role TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          prompt TEXT NOT NULL,
          hue INTEGER NOT NULL DEFAULT 220,
          glyph TEXT NOT NULL DEFAULT '◆',
          status_kind TEXT NOT NULL DEFAULT 'idle',
          status_label TEXT NOT NULL DEFAULT '在线待命',
          joined TEXT NOT NULL DEFAULT '今天入职',
          source TEXT NOT NULL DEFAULT 'custom',
          skills_json TEXT NOT NULL DEFAULT '[]',
          mcps_json TEXT NOT NULL DEFAULT '[]',
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conversations (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          kind TEXT NOT NULL CHECK(kind IN ('dm', 'group')),
          name TEXT NOT NULL DEFAULT '',
          agent_id TEXT REFERENCES agents(id) ON DELETE CASCADE,
          unread INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conversation_members (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
          UNIQUE(conversation_id, agent_id)
        );

        CREATE TABLE IF NOT EXISTS messages (
          id TEXT PRIMARY KEY,
          conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          sender_type TEXT NOT NULL CHECK(sender_type IN ('user', 'agent', 'system')),
          sender_id TEXT NOT NULL DEFAULT '',
          content TEXT NOT NULL,
          provider TEXT,
          model TEXT,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          title TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          priority TEXT NOT NULL DEFAULT 'P2',
          owner_agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
          status TEXT NOT NULL DEFAULT '进行中',
          progress INTEGER NOT NULL DEFAULT 0,
          conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
          due_date TEXT,
          parent_task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS knowledge_sources (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          title TEXT NOT NULL,
          category TEXT NOT NULL DEFAULT '通用资料',
          content TEXT NOT NULL,
          created_by TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS task_events (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
          conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
          agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
          kind TEXT NOT NULL,
          title TEXT NOT NULL,
          content TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS task_outputs (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
          conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
          agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
          title TEXT NOT NULL,
          output_type TEXT NOT NULL DEFAULT 'markdown',
          content TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS approvals (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
          task_id TEXT REFERENCES tasks(id) ON DELETE CASCADE,
          conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
          agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
          title TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'pending',
          risk_level TEXT NOT NULL DEFAULT 'medium',
          type TEXT NOT NULL DEFAULT 'high_risk'
            CHECK(type IN ('high_risk','clarification','capability_upgrade')),
          payload_json TEXT NOT NULL DEFAULT '{}',
          resolved_by TEXT NOT NULL DEFAULT '',
          resolved_at TEXT,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_experiences (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
          task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
          outcome TEXT NOT NULL,
          summary TEXT NOT NULL,
          lessons TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS consensus_briefs (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          discussion_conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'confirmed', 'rejected', 'superseded')),
          goal TEXT NOT NULL,
          scope TEXT NOT NULL DEFAULT '',
          constraints TEXT NOT NULL DEFAULT '',
          success_criteria TEXT NOT NULL DEFAULT '',
          owner_agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
          participant_agent_ids_json TEXT NOT NULL DEFAULT '[]',
          created_by_agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
          supersedes_brief_id TEXT REFERENCES consensus_briefs(id) ON DELETE SET NULL,
          derived_from_brief_id TEXT REFERENCES consensus_briefs(id) ON DELETE SET NULL,
          created_at TEXT NOT NULL,
          confirmed_at TEXT,
          confirmed_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS runs (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
          task_id TEXT REFERENCES tasks(id) ON DELETE CASCADE,
          status TEXT NOT NULL,
          input_message_id TEXT NOT NULL,
          output_message_id TEXT,
          hermes_profile_id TEXT,
          hermes_run_id TEXT,
          workdir TEXT,
          provider TEXT NOT NULL DEFAULT 'deepseek',
          model TEXT NOT NULL DEFAULT '',
          usage_json TEXT NOT NULL DEFAULT '{}',
          error TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS run_steps (
          id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
          type TEXT NOT NULL CHECK(type IN (
            'message','thinking','tool_call','tool_result',
            'approval_required','status','final'
          )),
          status TEXT NOT NULL DEFAULT '',
          title TEXT NOT NULL DEFAULT '',
          detail TEXT NOT NULL DEFAULT '',
          payload_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ideas (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          source_agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
          title TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          category TEXT NOT NULL CHECK(category IN (
            'improvement','opportunity','risk','learning'
          )),
          status TEXT NOT NULL DEFAULT 'new' CHECK(status IN (
            'new','reviewed','accepted','dismissed','converted'
          )),
          converted_brief_id TEXT REFERENCES consensus_briefs(id) ON DELETE SET NULL,
          created_at TEXT NOT NULL,
          reviewed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS channel_configs (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          channel_type TEXT NOT NULL CHECK(channel_type IN (
            'wechat','email','web_widget','generic_webhook'
          )),
          name TEXT NOT NULL,
          token TEXT NOT NULL UNIQUE,
          config_json TEXT NOT NULL DEFAULT '{}',
          target_agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
          target_conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_specs (
          id TEXT PRIMARY KEY,
          agent_id TEXT NOT NULL UNIQUE REFERENCES agents(id) ON DELETE CASCADE,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          role_name TEXT NOT NULL,
          source_request TEXT NOT NULL DEFAULT '',
          responsibilities_json TEXT NOT NULL DEFAULT '[]',
          hermes_profile TEXT,
          status TEXT NOT NULL DEFAULT 'draft'
            CHECK(status IN ('draft','provisioning','blocked_on_credentials','ready','failed')),
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_capabilities (
          id TEXT PRIMARY KEY,
          agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          capability_key TEXT NOT NULL,
          skill_refs_json TEXT NOT NULL DEFAULT '[]',
          toolset_refs_json TEXT NOT NULL DEFAULT '[]',
          mcp_refs_json TEXT NOT NULL DEFAULT '[]',
          required_credentials_json TEXT NOT NULL DEFAULT '[]',
          risk_gate TEXT NOT NULL DEFAULT 'auto'
            CHECK(risk_gate IN ('auto','approval','prohibited_auto')),
          status TEXT NOT NULL DEFAULT 'pending'
            CHECK(status IN ('pending','credential_missing','enabled','disabled')),
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(agent_id, capability_key)
        );
        """
    )
    ensure_column(conn, "messages", "provider", "TEXT")
    ensure_column(conn, "messages", "model", "TEXT")
    ensure_column(conn, "tasks", "description", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "tasks", "due_date", "TEXT")
    ensure_column(conn, "tasks", "parent_task_id", "TEXT REFERENCES tasks(id) ON DELETE SET NULL")
    ensure_column(conn, "tasks", "consensus_brief_id", "TEXT REFERENCES consensus_briefs(id) ON DELETE SET NULL")
    ensure_column(conn, "conversations", "discussion_status", "TEXT NOT NULL DEFAULT 'discussing' CHECK(discussion_status IN ('discussing', 'aligned'))")
    # TD-03-T1: Run/RunStep data model. New columns are nullable here; RunService
    # (TD-03-T3) enforces "every Run belongs to a Task" + absolute workdir at the
    # application layer once execution actually flows through Hermes.
    ensure_column(conn, "runs", "task_id", "TEXT REFERENCES tasks(id) ON DELETE CASCADE")
    ensure_column(conn, "runs", "hermes_profile_id", "TEXT")
    ensure_column(conn, "runs", "hermes_run_id", "TEXT")
    ensure_column(conn, "runs", "workdir", "TEXT")
    ensure_column(conn, "approvals", "run_id", "TEXT REFERENCES runs(id) ON DELETE SET NULL")
    ensure_column(
        conn,
        "approvals",
        "type",
        "TEXT NOT NULL DEFAULT 'high_risk' "
        "CHECK(type IN ('high_risk','clarification','capability_upgrade'))",
    )
    ensure_column(
        conn, "approvals", "payload_json", "TEXT NOT NULL DEFAULT '{}'"
    )
    ensure_column(conn, "agents", "hermes_gateway_port", "INTEGER")
    # TD-08-T1: idea center (idle reflection). idle_thinking_enabled stored as
    # 0/1 INTEGER in both dialects (serialized to bool at the API layer).
    ensure_column(conn, "agent_specs", "last_idle_think_at", "TEXT")
    ensure_column(
        conn, "agent_specs", "idle_think_interval_hours", "INTEGER NOT NULL DEFAULT 6"
    )
    ensure_column(
        conn, "agent_specs", "idle_thinking_enabled", "INTEGER NOT NULL DEFAULT 1"
    )
    # TD-06-T1: skill self-sedimentation (reflection cron).
    ensure_column(
        conn, "agent_specs", "runs_since_last_reflection", "INTEGER NOT NULL DEFAULT 0"
    )
    ensure_column(conn, "agent_specs", "last_skill_reflection_at", "TEXT")
    ensure_column(
        conn, "agent_specs", "reflection_interval", "INTEGER NOT NULL DEFAULT 5"
    )
    ensure_column(
        conn, "conversations", "idea_id", "TEXT REFERENCES ideas(id) ON DELETE SET NULL"
    )
    # TD-09-T1: external channel adapters. Conversations remember which channel
    # (and external thread) they came from; messages carry the external id for
    # webhook-redelivery dedup.
    ensure_column(conn, "conversations", "source_channel", "TEXT")
    ensure_column(conn, "conversations", "external_conversation_id", "TEXT")
    ensure_column(conn, "messages", "external_message_id", "TEXT")


def ensure_column(
    conn: Database, table_name: str, column_name: str, definition: str
) -> None:
    if conn.dialect == "postgres":
        exists = conn.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = ? AND column_name = ?
            """,
            (table_name, column_name),
        ).fetchone()
        if exists is not None:
            return
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
        return

    columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    if any(column["name"] == column_name for column in columns):
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def reset_database_for_tests() -> None:
    conn = connect()
    try:
        if conn.dialect == "postgres":
            conn.executescript(
                """
                DROP TABLE IF EXISTS runs CASCADE;
                DROP TABLE IF EXISTS agent_experiences CASCADE;
                DROP TABLE IF EXISTS approvals CASCADE;
                DROP TABLE IF EXISTS task_outputs CASCADE;
                DROP TABLE IF EXISTS task_events CASCADE;
                DROP TABLE IF EXISTS knowledge_sources CASCADE;
                DROP TABLE IF EXISTS tasks CASCADE;
                DROP TABLE IF EXISTS messages CASCADE;
                DROP TABLE IF EXISTS conversation_members CASCADE;
                DROP TABLE IF EXISTS conversations CASCADE;
                DROP TABLE IF EXISTS agents CASCADE;
                DROP TABLE IF EXISTS departments CASCADE;
                DROP TABLE IF EXISTS workspaces CASCADE;
                DROP TABLE IF EXISTS users CASCADE;
                DROP TABLE IF EXISTS official_agent_templates CASCADE;
                DROP TABLE IF EXISTS official_talent_categories CASCADE;
                """
            )
        else:
            conn.executescript(
                """
                DROP TABLE IF EXISTS runs;
                DROP TABLE IF EXISTS agent_experiences;
                DROP TABLE IF EXISTS approvals;
                DROP TABLE IF EXISTS task_outputs;
                DROP TABLE IF EXISTS task_events;
                DROP TABLE IF EXISTS knowledge_sources;
                DROP TABLE IF EXISTS tasks;
                DROP TABLE IF EXISTS messages;
                DROP TABLE IF EXISTS conversation_members;
                DROP TABLE IF EXISTS conversations;
                DROP TABLE IF EXISTS agents;
                DROP TABLE IF EXISTS departments;
                DROP TABLE IF EXISTS workspaces;
                DROP TABLE IF EXISTS users;
                DROP TABLE IF EXISTS official_agent_templates;
                DROP TABLE IF EXISTS official_talent_categories;
                """
            )
        conn.commit()
    finally:
        conn.close()


def split_sql_script(script: str) -> list[str]:
    return [statement.strip() for statement in script.split(";") if statement.strip()]


def database_kind() -> str:
    return "sqlite" if is_sqlite_url(settings.database_url) else "postgres"


def safe_database_label() -> str:
    parsed = urlparse(settings.database_url)
    if parsed.scheme.startswith("sqlite"):
        return str(sqlite_path(settings.database_url))
    host = parsed.hostname or "localhost"
    port = f":{parsed.port}" if parsed.port else ""
    database = parsed.path.lstrip("/") or "postgres"
    return f"{parsed.scheme}://{host}{port}/{database}"


def validate_identifier(identifier: str) -> None:
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", identifier):
        raise ValueError(f"unsafe SQL identifier: {identifier}")
