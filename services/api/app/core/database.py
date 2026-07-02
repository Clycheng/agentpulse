from __future__ import annotations

from collections.abc import Generator, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import re
import sqlite3

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings


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
        translated_sql = sql.replace("?", "%s")
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


def connect() -> Database:
    database_url = settings.database_url
    if is_sqlite_url(database_url):
        return connect_sqlite(database_url)
    conn = psycopg.connect(database_url, row_factory=dict_row)
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


def init_db() -> None:
    conn = connect()
    try:
        if conn.dialect == "postgres":
            init_postgres(conn)
        else:
            init_sqlite(conn)
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

        CREATE TABLE IF NOT EXISTS runs (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
          status TEXT NOT NULL,
          input_message_id TEXT NOT NULL,
          output_message_id TEXT,
          provider TEXT NOT NULL DEFAULT 'deepseek',
          model TEXT NOT NULL DEFAULT '',
          usage_json TEXT NOT NULL DEFAULT '{}',
          error TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          completed_at TEXT
        );
        """
    )
    ensure_column(conn, "messages", "provider", "TEXT")
    ensure_column(conn, "messages", "model", "TEXT")
    ensure_column(conn, "tasks", "description", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "tasks", "due_date", "TEXT")
    ensure_column(conn, "tasks", "parent_task_id", "TEXT REFERENCES tasks(id) ON DELETE SET NULL")


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

        CREATE TABLE IF NOT EXISTS runs (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
          conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
          status TEXT NOT NULL,
          input_message_id TEXT NOT NULL,
          output_message_id TEXT,
          provider TEXT NOT NULL DEFAULT 'deepseek',
          model TEXT NOT NULL DEFAULT '',
          usage_json TEXT NOT NULL DEFAULT '{}',
          error TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          completed_at TEXT
        );
        """
    )
    ensure_column(conn, "messages", "provider", "TEXT")
    ensure_column(conn, "messages", "model", "TEXT")
    ensure_column(conn, "tasks", "description", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "tasks", "due_date", "TEXT")
    ensure_column(conn, "tasks", "parent_task_id", "TEXT REFERENCES tasks(id) ON DELETE SET NULL")


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
                DROP TABLE IF EXISTS tasks CASCADE;
                DROP TABLE IF EXISTS messages CASCADE;
                DROP TABLE IF EXISTS conversation_members CASCADE;
                DROP TABLE IF EXISTS conversations CASCADE;
                DROP TABLE IF EXISTS agents CASCADE;
                DROP TABLE IF EXISTS departments CASCADE;
                DROP TABLE IF EXISTS workspaces CASCADE;
                DROP TABLE IF EXISTS users CASCADE;
                """
            )
        else:
            conn.executescript(
                """
                DROP TABLE IF EXISTS runs;
                DROP TABLE IF EXISTS tasks;
                DROP TABLE IF EXISTS messages;
                DROP TABLE IF EXISTS conversation_members;
                DROP TABLE IF EXISTS conversations;
                DROP TABLE IF EXISTS agents;
                DROP TABLE IF EXISTS departments;
                DROP TABLE IF EXISTS workspaces;
                DROP TABLE IF EXISTS users;
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
