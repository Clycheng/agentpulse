"""Tests for HermesBackend (TD-03-T2, ACP transport per ADR 0007).

The e2e test drives real Hermes over ACP and calls DeepSeek, so it is SKIPPED by
default. To run it you need Hermes installed, the `agentpulse` profile
provisioned with a DeepSeek key, and an agentpulse-anchored shell (ADR 0005):

    HERMES_E2E=1 pytest tests/test_hermes_backend.py

The always-on tests cover the ADR 0005 safety invariants without touching Hermes.
"""

import asyncio
import os
import shutil
import tempfile

import pytest

from app.runtime.hermes_client import (
    AgentEvent,
    HermesBackend,
    HermesBackendError,
    RunContext,
    _safe_path,
)

_E2E = os.environ.get("HERMES_E2E") == "1" and shutil.which("hermes") is not None
requires_hermes = pytest.mark.skipif(
    not _E2E, reason="set HERMES_E2E=1 with hermes + agentpulse profile to run"
)


# --- Always-on: safety invariants ---

def test_relative_workdir_rejected():
    be = HermesBackend()
    ctx = RunContext(
        run_id="r", prompt="hi", workdir="relative/dir", profile="agentpulse"
    )
    gen = be.run(ctx)
    with pytest.raises(HermesBackendError):
        asyncio.run(gen.__anext__())


def test_safe_path_blocks_escape():
    from pathlib import Path

    # resolve() up front — macOS tempdirs live under a /var -> /private/var symlink
    root = str(Path(tempfile.mkdtemp()).resolve())
    # inside is fine
    assert str(_safe_path(root, "notes.txt")).startswith(root)
    # escaping is refused
    with pytest.raises(HermesBackendError):
        _safe_path(root, "../../etc/passwd")


# --- E2E: real Hermes over ACP ---

@requires_hermes
def test_run_reaches_final_with_message():
    work = tempfile.mkdtemp(prefix="ap-hermes-run-")
    be = HermesBackend()
    ctx = RunContext(
        run_id="run_e2e",
        prompt="Reply with exactly: OK",
        workdir=work,
        profile="agentpulse",
        timeout=120,
    )

    async def collect() -> list[AgentEvent]:
        return [ev async for ev in be.run(ctx)]

    events = asyncio.run(collect())
    types = [e.type for e in events]
    assert "final" in types
    assert types[-1] == "final"
    assert any(e.type == "message" for e in events)
    # message chunks carry the reply text
    text = "".join(
        e.payload.get("content", {}).get("text", "")
        for e in events
        if e.type == "message"
    )
    assert "OK" in text
