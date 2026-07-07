"""Tests for agent_specs/agent_capabilities tables and DTOs (TD-04-T1).

Verifies:
- Tables exist in both sqlite and postgres init paths
- CHECK constraints on status/risk_gate
- UNIQUE(agent_id, capability_key)
- agent_specs.agent_id is UNIQUE (1:1)
- CASCADE on agent delete
"""

import json

import pytest

from app.core.config import settings
from app.core.database import connect, init_db
from app.schemas.agent_spec import (
    AgentCapabilityOut,
    AgentSpecOut,
    RoleSpecIn,
)
from app.services.workspace import new_id, now_iso


def make_client(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings,
        "database_url",
        f"sqlite:///{tmp_path / 'agentpulse.sqlite3'}",
    )
    monkeypatch.setattr(settings, "password_iterations", 1_000)
    init_db()


def create_workspace_and_agent():
    """Create a workspace and agent for testing."""
    conn = connect()
    try:
        workspace_id = new_id("wk")
        user_id = new_id("user")
        agent_id = new_id("agent")
        dept_id = new_id("dept")
        created_at = now_iso()

        conn.execute(
            "INSERT INTO users (id, email, password_hash, display_name, created_at) VALUES (?, ?, '', 'test', ?)",
            (user_id, f"test_{agent_id}@example.com", created_at),
        )
        conn.execute(
            "INSERT INTO workspaces (id, owner_user_id, name, onboarding_completed, created_at) VALUES (?, ?, 'test', 1, ?)",
            (workspace_id, user_id, created_at),
        )
        conn.execute(
            "INSERT INTO departments (id, workspace_id, name, sort_order, created_at) VALUES (?, ?, 'test', 0, ?)",
            (dept_id, workspace_id, created_at),
        )
        conn.execute(
            """INSERT INTO agents
            (id, workspace_id, department_id, name, role, description, prompt,
             hue, glyph, status_kind, status_label, joined, source, skills_json, mcps_json)
            VALUES (?, ?, ?, 'TestAgent', 'test', 'test', 'test', 0, 'A', 'idle', '', ?, 'custom', '[]', '[]')
            """,
            (agent_id, workspace_id, dept_id, created_at),
        )
        conn.commit()
        return workspace_id, agent_id
    finally:
        conn.close()


class TestTablesExist:
    def test_agent_specs_table_exists(self, tmp_path, monkeypatch):
        make_client(tmp_path, monkeypatch)
        conn = connect()
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_specs'"
            ).fetchone()
            assert row is not None
        finally:
            conn.close()

    def test_agent_capabilities_table_exists(self, tmp_path, monkeypatch):
        make_client(tmp_path, monkeypatch)
        conn = connect()
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_capabilities'"
            ).fetchone()
            assert row is not None
        finally:
            conn.close()


class TestAgentSpecConstraints:
    def test_insert_valid_spec(self, tmp_path, monkeypatch):
        make_client(tmp_path, monkeypatch)
        workspace_id, agent_id = create_workspace_and_agent()
        conn = connect()
        try:
            spec_id = new_id("spec")
            created_at = now_iso()
            conn.execute(
                """INSERT INTO agent_specs
                (id, agent_id, workspace_id, role_name, source_request,
                 responsibilities_json, status, created_at, updated_at)
                VALUES (?, ?, ?, '前端工程师', '我要一个前端工程师', '[]', 'draft', ?, ?)
                """,
                (spec_id, agent_id, workspace_id, created_at, created_at),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM agent_specs WHERE id = ?", (spec_id,)
            ).fetchone()
            assert row["role_name"] == "前端工程师"
            assert row["status"] == "draft"
        finally:
            conn.close()

    def test_agent_id_unique(self, tmp_path, monkeypatch):
        make_client(tmp_path, monkeypatch)
        workspace_id, agent_id = create_workspace_and_agent()
        conn = connect()
        try:
            spec_id1 = new_id("spec")
            created_at = now_iso()
            conn.execute(
                """INSERT INTO agent_specs
                (id, agent_id, workspace_id, role_name, status, created_at, updated_at)
                VALUES (?, ?, ?, 'role1', 'draft', ?, ?)
                """,
                (spec_id1, agent_id, workspace_id, created_at, created_at),
            )
            conn.commit()
            # Second spec for same agent should fail
            spec_id2 = new_id("spec")
            with pytest.raises(Exception):
                conn.execute(
                    """INSERT INTO agent_specs
                    (id, agent_id, workspace_id, role_name, status, created_at, updated_at)
                    VALUES (?, ?, ?, 'role2', 'draft', ?, ?)
                    """,
                    (spec_id2, agent_id, workspace_id, created_at, created_at),
                )
                conn.commit()
        finally:
            conn.close()

    def test_invalid_status_rejected(self, tmp_path, monkeypatch):
        make_client(tmp_path, monkeypatch)
        workspace_id, agent_id = create_workspace_and_agent()
        conn = connect()
        try:
            spec_id = new_id("spec")
            created_at = now_iso()
            with pytest.raises(Exception):
                conn.execute(
                    """INSERT INTO agent_specs
                    (id, agent_id, workspace_id, role_name, status, created_at, updated_at)
                    VALUES (?, ?, ?, 'role', 'bogus_status', ?, ?)
                    """,
                    (spec_id, agent_id, workspace_id, created_at, created_at),
                )
                conn.commit()
        finally:
            conn.close()

    def test_cascade_on_agent_delete(self, tmp_path, monkeypatch):
        make_client(tmp_path, monkeypatch)
        workspace_id, agent_id = create_workspace_and_agent()
        conn = connect()
        try:
            spec_id = new_id("spec")
            created_at = now_iso()
            conn.execute(
                """INSERT INTO agent_specs
                (id, agent_id, workspace_id, role_name, status, created_at, updated_at)
                VALUES (?, ?, ?, 'role', 'draft', ?, ?)
                """,
                (spec_id, agent_id, workspace_id, created_at, created_at),
            )
            conn.commit()
            # Delete agent → spec should cascade
            conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM agent_specs WHERE id = ?", (spec_id,)
            ).fetchone()
            assert row is None
        finally:
            conn.close()


class TestAgentCapabilityConstraints:
    def test_insert_valid_capability(self, tmp_path, monkeypatch):
        make_client(tmp_path, monkeypatch)
        workspace_id, agent_id = create_workspace_and_agent()
        conn = connect()
        try:
            cap_id = new_id("cap")
            created_at = now_iso()
            conn.execute(
                """INSERT INTO agent_capabilities
                (id, agent_id, workspace_id, capability_key,
                 skill_refs_json, toolset_refs_json, mcp_refs_json,
                 required_credentials_json, risk_gate, status, created_at, updated_at)
                VALUES (?, ?, ?, 'write_code', '[]', '[]', '[]', '[]', 'auto', 'pending', ?, ?)
                """,
                (cap_id, agent_id, workspace_id, created_at, created_at),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM agent_capabilities WHERE id = ?", (cap_id,)
            ).fetchone()
            assert row["capability_key"] == "write_code"
            assert row["risk_gate"] == "auto"
        finally:
            conn.close()

    def test_unique_agent_capability(self, tmp_path, monkeypatch):
        """UNIQUE(agent_id, capability_key) — same key twice for same agent fails."""
        make_client(tmp_path, monkeypatch)
        workspace_id, agent_id = create_workspace_and_agent()
        conn = connect()
        try:
            created_at = now_iso()
            for i in range(2):
                conn.execute(
                    """INSERT INTO agent_capabilities
                    (id, agent_id, workspace_id, capability_key,
                     risk_gate, status, created_at, updated_at)
                    VALUES (?, ?, ?, 'write_code', 'auto', 'pending', ?, ?)
                    """,
                    (new_id("cap"), agent_id, workspace_id, created_at, created_at),
                )
            with pytest.raises(Exception):
                conn.commit()
        finally:
            conn.close()

    def test_invalid_risk_gate_rejected(self, tmp_path, monkeypatch):
        make_client(tmp_path, monkeypatch)
        workspace_id, agent_id = create_workspace_and_agent()
        conn = connect()
        try:
            cap_id = new_id("cap")
            created_at = now_iso()
            with pytest.raises(Exception):
                conn.execute(
                    """INSERT INTO agent_capabilities
                    (id, agent_id, workspace_id, capability_key,
                     risk_gate, status, created_at, updated_at)
                    VALUES (?, ?, ?, 'write_code', 'bogus', 'pending', ?, ?)
                    """,
                    (cap_id, agent_id, workspace_id, created_at, created_at),
                )
                conn.commit()
        finally:
            conn.close()

    def test_invalid_capability_status_rejected(self, tmp_path, monkeypatch):
        make_client(tmp_path, monkeypatch)
        workspace_id, agent_id = create_workspace_and_agent()
        conn = connect()
        try:
            cap_id = new_id("cap")
            created_at = now_iso()
            with pytest.raises(Exception):
                conn.execute(
                    """INSERT INTO agent_capabilities
                    (id, agent_id, workspace_id, capability_key,
                     risk_gate, status, created_at, updated_at)
                    VALUES (?, ?, ?, 'write_code', 'auto', 'bogus', ?, ?)
                    """,
                    (cap_id, agent_id, workspace_id, created_at, created_at),
                )
                conn.commit()
        finally:
            conn.close()


class TestDTOs:
    def test_role_spec_in_validation(self):
        spec = RoleSpecIn(
            role_name="前端工程师",
            source_request="我要一个能写React的前端",
            responsibilities=["写组件", "写测试"],
            capability_keys=["write_code", "run_tests"],
        )
        assert spec.role_name == "前端工程师"
        assert len(spec.responsibilities) == 2

    def test_role_spec_in_role_name_max_length(self):
        with pytest.raises(Exception):
            RoleSpecIn(role_name="x" * 81)

    def test_role_spec_in_responsibilities_max_length(self):
        with pytest.raises(Exception):
            RoleSpecIn(role_name="test", responsibilities=["x"] * 13)

    def test_agent_spec_out_serialization(self):
        spec = AgentSpecOut(
            id="spec_123",
            agent_id="agent_456",
            workspace_id="wk_789",
            role_name="前端工程师",
            source_request="",
            responsibilities=["写代码"],
            hermes_profile=None,
            status="draft",
            capabilities=[],
            created_at="2026-07-07T00:00:00Z",
            updated_at="2026-07-07T00:00:00Z",
        )
        assert spec.status == "draft"
        assert spec.capabilities == []

    def test_agent_capability_out_serialization(self):
        cap = AgentCapabilityOut(
            id="cap_123",
            agent_id="agent_456",
            capability_key="write_code",
            skill_refs=[],
            toolset_refs=["terminal", "file"],
            mcp_refs=[],
            required_credentials=[],
            risk_gate="auto",
            status="pending",
            created_at="2026-07-07T00:00:00Z",
            updated_at="2026-07-07T00:00:00Z",
        )
        assert cap.capability_key == "write_code"
        assert cap.risk_gate == "auto"
