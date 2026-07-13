"""Real integration test for LocalHermesProvisioner (TD-04-T6).

Drives the actual `hermes` CLI, so it is SKIPPED by default. To run it you need
Hermes installed and an agentpulse-anchored shell (ADR 0005):

    HERMES_E2E=1 pytest tests/test_local_provisioner.py

It uses a throwaway profile and deletes it afterwards; it does NOT call the LLM
(create/configure are free), so it costs nothing. The always-on tests below
cover the safety invariants without touching Hermes.
"""

import os
import shutil
import tempfile

import pytest

from app.runtime.profile_provisioner import (
    HermesProvisionError,
    LocalHermesProvisioner,
)

_E2E = os.environ.get("HERMES_E2E") == "1" and shutil.which("hermes") is not None
requires_hermes = pytest.mark.skipif(
    not _E2E, reason="set HERMES_E2E=1 with hermes installed to run"
)


# --- Always-on: safety invariants (no Hermes needed) ---

def test_work_root_must_be_absolute():
    with pytest.raises(HermesProvisionError):
        LocalHermesProvisioner(work_root="relative/path")


def test_missing_hermes_binary_raises():
    prov = LocalHermesProvisioner(
        work_root=tempfile.gettempdir(), hermes_bin="hermes-does-not-exist-xyz"
    )
    with pytest.raises(HermesProvisionError, match="not found"):
        prov.create_profile("whatever")


# --- E2E: real hermes CLI ---

@requires_hermes
def test_provision_and_teardown_real_profile():
    work_root = tempfile.mkdtemp(prefix="ap-hermes-e2e-")
    prov = LocalHermesProvisioner(work_root=work_root)
    name = "aptest_e2e"
    try:
        prov.create_profile(name)
        prov.create_profile(name)  # idempotent — no error on repeat
        prov.configure(
            name,
            model="deepseek/deepseek-v4-flash",
            toolsets=["web", "memory"],
            mcp=[],
        )
        prov.write_soul(name, "# 测试员工\n用于 e2e 验证。")
        prov.write_credentials(name, {"DEEPSEEK_API_KEY": "sk-fake"})

        pdir = prov._profile_dir(name)
        config = (pdir / "config.yaml").read_text()
        assert "deepseek-v4-flash" in config
        assert work_root in config  # absolute workdir bound (ADR 0005)
        assert (pdir / "SOUL.md").exists()
        assert "DEEPSEEK_API_KEY" in (pdir / ".env").read_text()
    finally:
        prov.delete_profile(name)
        assert not prov._profile_exists(name)
