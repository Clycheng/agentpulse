"""Auto-provisioning wiring (TD-03-T5): create_agent_spec -> provision.

Always-on tests use a RecordOnly provisioner to assert the wiring (SOUL +
credentials written, model, profile-name shape). The guarded e2e drives the real
`hermes` CLI to prove "hire -> a runnable Hermes profile exists".

    HERMES_E2E=1 pytest tests/test_auto_provision.py
"""

import os
import shutil
import sqlite3
import tempfile

import pytest

from app.core.config import settings
from app.core.database import Database
from app.orchestration.supply import create_agent_spec, provision
from app.runtime.profile_provisioner import (
    LocalHermesProvisioner,
    RecordOnlyProvisioner,
)


def _make_db() -> Database:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db = Database(conn, "sqlite")
    db.executescript(
        """
        CREATE TABLE workspaces (id TEXT PRIMARY KEY, name TEXT);
        CREATE TABLE agents (
            id TEXT PRIMARY KEY, workspace_id TEXT, name TEXT, role TEXT,
            description TEXT, prompt TEXT
        );
        CREATE TABLE agent_specs (
            id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
            role_name TEXT NOT NULL, source_request TEXT NOT NULL DEFAULT '',
            responsibilities_json TEXT NOT NULL DEFAULT '[]', hermes_profile TEXT,
            status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE agent_capabilities (
            id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
            capability_key TEXT NOT NULL, skill_refs_json TEXT NOT NULL DEFAULT '[]',
            toolset_refs_json TEXT NOT NULL DEFAULT '[]', mcp_refs_json TEXT NOT NULL DEFAULT '[]',
            required_credentials_json TEXT NOT NULL DEFAULT '[]',
            risk_gate TEXT NOT NULL DEFAULT 'auto', status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        INSERT INTO workspaces (id, name) VALUES ('ws_1', '测试公司');
        INSERT INTO agents (id, workspace_id, name, role, description, prompt)
        VALUES ('agent_abc123', 'ws_1', '小研', '研究员', '做研究', '你负责调研并输出结论');
        """
    )
    return db


def _spec_with_auto_cap(db: Database):
    create_agent_spec(
        db,
        agent_id="agent_abc123",
        workspace_id="ws_1",
        role_name="研究员",
        responsibilities=["调研", "写报告"],
        capability_keys=["content_writing"],  # auto, no credentials
    )


def test_wiring_records_soul_and_credentials(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-fake-test")
    db = _make_db()
    _spec_with_auto_cap(db)
    rec = RecordOnlyProvisioner()
    spec = provision(db, "agent_abc123", provisioner=rec)

    assert spec["status"] == "ready"
    profile = spec["hermes_profile"]
    assert profile and profile.replace("_", "").isalnum() and profile.islower()

    actions = [a.action for a in rec.get_actions()]
    assert actions[:2] == ["create_profile", "write_soul"]
    assert "configure" in actions
    assert "write_credentials" in actions  # DeepSeek key handed to the profile
    # credential values are never recorded, only key names
    wc = next(a for a in rec.get_actions() if a.action == "write_credentials")
    assert wc.details["credential_keys"] == ["DEEPSEEK_API_KEY"]


def test_default_provisioner_is_record_only_when_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "hermes_provisioning", False)
    from app.runtime.profile_provisioner import build_provisioner_from_settings

    assert isinstance(build_provisioner_from_settings(), RecordOnlyProvisioner)


_E2E = os.environ.get("HERMES_E2E") == "1" and shutil.which("hermes") is not None


@pytest.mark.skipif(not _E2E, reason="set HERMES_E2E=1 with hermes installed")
def test_hire_creates_runnable_profile(monkeypatch):
    work_root = tempfile.mkdtemp(prefix="ap-autoprov-")
    monkeypatch.setattr(settings, "hermes_provisioning", True)
    monkeypatch.setattr(settings, "hermes_work_root", work_root)
    if not settings.deepseek_api_key:
        monkeypatch.setattr(settings, "deepseek_api_key", "sk-placeholder")

    db = _make_db()
    _spec_with_auto_cap(db)
    prov = LocalHermesProvisioner(work_root=work_root)
    try:
        spec = provision(db, "agent_abc123")  # uses config-driven LocalHermes
        assert spec["status"] == "ready"
        profile = spec["hermes_profile"]

        pdir = prov._profile_dir(profile)
        config = (pdir / "config.yaml").read_text()
        assert "deepseek-v4-flash" in config
        assert (pdir / "SOUL.md").exists()
        assert "研究员" in (pdir / "SOUL.md").read_text()
        assert "DEEPSEEK_API_KEY" in (pdir / ".env").read_text()
    finally:
        prov.delete_profile(spec["hermes_profile"] if "spec" in dir() else "")
