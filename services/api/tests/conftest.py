"""Global test isolation: never leak local credentials or real runtimes."""

from __future__ import annotations

import os
import socket

import pytest


if os.environ.get("HERMES_E2E") != "1":
    os.environ["AGENTPULSE_DEEPSEEK_API_KEY"] = ""
    os.environ["AGENTPULSE_HERMES_PROVISIONING"] = "false"
    os.environ["AGENTPULSE_TASK_WORKER_ENABLED"] = "false"

os.environ.setdefault("AGENTPULSE_AUTH_RATE_LIMIT_ENABLED", "false")

os.environ.setdefault("AGENTPULSE_ALLOW_DEFAULT_SECRET", "1")


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch):
    if os.environ.get("HERMES_E2E") == "1":
        return
    original_connect = socket.socket.connect

    def guarded_connect(sock, address):
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise RuntimeError(f"external network disabled in tests: {host}")
        return original_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
