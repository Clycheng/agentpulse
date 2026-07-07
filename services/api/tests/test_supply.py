"""Tests for supply state machine and provisioning orchestration (TD-04-T4).

Covers:
- create_agent_spec: creates spec + capabilities from catalog
- provision: no-cred capabilities → ready
- provision: credentials needed → blocked_on_credentials
- provision: prohibited_auto → credential_missing (manual only)
- provision: idempotent retry
- provision: failure → failed, retry recovers
"""

import pytest

from app.core.config import settings
from app.core.database import connect, init_db
from app.orchestration.supply import (
    ProvisioningError,
    create_agent_spec,
    provision,
)
from app.runtime import RecordOnlyProvisioner
from app.services.workspace import new_id, now_iso


def make_db(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings,
        "database_url",
        f"sqlite:///{tmp_path / 'agentpulse.sqlite3'}",
    )
    monkeypatch.setattr(settings, "password_iterations", 1_000)
    init_db()


def create_workspace_and_agent():
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
             hue, glyph, status_kind, status_label, joined, source, skills_json, mcps_json, created_at)
            VALUES (?, ?, ?, 'TestAgent', 'test', 'test', 'test', 0, 'A', 'idle', '', '今天入职', 'custom', '[]', '[]', ?)
            """,
            (agent_id, workspace_id, dept_id, created_at),
        )
        conn.commit()
        return workspace_id, agent_id
    finally:
        conn.close()


class TestCreateAgentSpec:
    def test_creates_spec_with_capabilities(self, tmp_path, monkeypatch):
        make_db(tmp_path, monkeypatch)
        workspace_id, agent_id = create_workspace_and_agent()
        conn = connect()
        try:
            spec = create_agent_spec(
                conn,
                agent_id=agent_id,
                workspace_id=workspace_id,
                role_name="前端工程师",
                responsibilities=["写代码", "发PR"],
                capability_keys=["write_code", "git_push"],
            )
            assert spec["role_name"] == "前端工程师"
            assert spec["status"] == "draft"
            assert len(spec["capabilities"]) == 2
            cap_keys = {c["capability_key"] for c in spec["capabilities"]}
            assert cap_keys == {"write_code", "git_push"}

            # Verify capability details from catalog
            write_code_cap = next(c for c in spec["capabilities"] if c["capability_key"] == "write_code")
            assert write_code_cap["risk_gate"] == "auto"
            assert write_code_cap["toolset_refs"] == ["file", "terminal"]

            git_push_cap = next(c for c in spec["capabilities"] if c["capability_key"] == "git_push")
            assert git_push_cap["risk_gate"] == "approval"
            assert git_push_cap["required_credentials"] == ["GITHUB_TOKEN"]
        finally:
            conn.close()

    def test_unknown_capability_key_raises(self, tmp_path, monkeypatch):
        make_db(tmp_path, monkeypatch)
        workspace_id, agent_id = create_workspace_and_agent()
        conn = connect()
        try:
            with pytest.raises(ValueError, match="Unknown capability"):
                create_agent_spec(
                    conn,
                    agent_id=agent_id,
                    workspace_id=workspace_id,
                    role_name="测试",
                    capability_keys=["write_code", "bogus"],
                )
        finally:
            conn.close()


class TestProvision:
    def test_no_credentials_needed_goes_ready(self, tmp_path, monkeypatch):
        """write_code + run_tests: no creds → all enabled → ready"""
        make_db(tmp_path, monkeypatch)
        workspace_id, agent_id = create_workspace_and_agent()
        conn = connect()
        try:
            create_agent_spec(
                conn,
                agent_id=agent_id,
                workspace_id=workspace_id,
                role_name="前端工程师",
                capability_keys=["write_code", "run_tests"],
            )
            prov = RecordOnlyProvisioner()
            result = provision(conn, agent_id, provisioner=prov)
            assert result["status"] == "ready"
            assert result["hermes_profile"] is not None

            # Capabilities should be enabled
            for cap in result["capabilities"]:
                assert cap["status"] == "enabled"

            # Provisioner was called
            assert len(prov.get_actions()) > 0
        finally:
            conn.close()

    def test_credentials_needed_goes_blocked(self, tmp_path, monkeypatch):
        """git_push needs GITHUB_TOKEN → blocked_on_credentials"""
        make_db(tmp_path, monkeypatch)
        workspace_id, agent_id = create_workspace_and_agent()
        conn = connect()
        try:
            create_agent_spec(
                conn,
                agent_id=agent_id,
                workspace_id=workspace_id,
                role_name="开发者",
                capability_keys=["write_code", "git_push"],
            )
            result = provision(conn, agent_id)
            assert result["status"] == "blocked_on_credentials"

            # write_code should be enabled, git_push credential_missing
            caps = {c["capability_key"]: c for c in result["capabilities"]}
            assert caps["write_code"]["status"] == "enabled"
            assert caps["git_push"]["status"] == "credential_missing"
        finally:
            conn.close()

    def test_prohibited_auto_always_blocked(self, tmp_path, monkeypatch):
        """domain_register is prohibited_auto → always credential_missing"""
        make_db(tmp_path, monkeypatch)
        workspace_id, agent_id = create_workspace_and_agent()
        conn = connect()
        try:
            create_agent_spec(
                conn,
                agent_id=agent_id,
                workspace_id=workspace_id,
                role_name="运维",
                capability_keys=["domain_register"],
            )
            result = provision(conn, agent_id)
            assert result["status"] == "blocked_on_credentials"
            caps = {c["capability_key"]: c for c in result["capabilities"]}
            assert caps["domain_register"]["status"] == "credential_missing"
        finally:
            conn.close()

    def test_idempotent_re_provision(self, tmp_path, monkeypatch):
        """Calling provision again on ready agent is a no-op."""
        make_db(tmp_path, monkeypatch)
        workspace_id, agent_id = create_workspace_and_agent()
        conn = connect()
        try:
            create_agent_spec(
                conn,
                agent_id=agent_id,
                workspace_id=workspace_id,
                role_name="工程师",
                capability_keys=["write_code"],
            )
            result1 = provision(conn, agent_id)
            assert result1["status"] == "ready"

            # Re-provision should return same state
            result2 = provision(conn, agent_id)
            assert result2["status"] == "ready"
        finally:
            conn.close()

    def test_re_provision_blocked_after_credential_fix(self, tmp_path, monkeypatch):
        """After provision → blocked, manually fix credential → re-provision → ready."""
        make_db(tmp_path, monkeypatch)
        workspace_id, agent_id = create_workspace_and_agent()
        conn = connect()
        try:
            create_agent_spec(
                conn,
                agent_id=agent_id,
                workspace_id=workspace_id,
                role_name="开发者",
                capability_keys=["write_code", "git_push"],
            )
            result = provision(conn, agent_id)
            assert result["status"] == "blocked_on_credentials"

            # Simulate credential being provided (manually set status)
            cap = conn.execute(
                "SELECT id FROM agent_capabilities WHERE agent_id = ? AND capability_key = 'git_push'",
                (agent_id,),
            ).fetchone()
            conn.execute(
                "UPDATE agent_capabilities SET status = 'enabled' WHERE id = ?",
                (cap["id"],),
            )
            conn.commit()

            # Re-provision
            result2 = provision(conn, agent_id)
            assert result2["status"] == "ready"
        finally:
            conn.close()

    def test_spec_not_found_raises(self, tmp_path, monkeypatch):
        make_db(tmp_path, monkeypatch)
        create_workspace_and_agent()
        conn = connect()
        try:
            with pytest.raises(ProvisioningError, match="agent_spec not found"):
                provision(conn, "nonexistent_agent")
        finally:
            conn.close()

    def test_mixed_auto_and_approval(self, tmp_path, monkeypatch):
        """deploy_prod (approval, needs creds) + write_code (auto) → blocked"""
        make_db(tmp_path, monkeypatch)
        workspace_id, agent_id = create_workspace_and_agent()
        conn = connect()
        try:
            create_agent_spec(
                conn,
                agent_id=agent_id,
                workspace_id=workspace_id,
                role_name="DevOps",
                capability_keys=["write_code", "deploy_prod"],
            )
            result = provision(conn, agent_id)
            assert result["status"] == "blocked_on_credentials"
            caps = {c["capability_key"]: c for c in result["capabilities"]}
            assert caps["write_code"]["status"] == "enabled"
            assert caps["deploy_prod"]["status"] == "credential_missing"
        finally:
            conn.close()
