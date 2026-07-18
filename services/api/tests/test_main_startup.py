"""Startup smoke checks (borrowed from service-claw-cloud's lifespan pattern:
fail loud at boot, not on the first request that needed the missing thing)."""

import pytest

from app.core.config import settings
from app.main import _check_hermes_binary_if_provisioning_enabled


def test_noop_when_provisioning_disabled(monkeypatch):
    monkeypatch.setattr(settings, "hermes_provisioning", False)
    _check_hermes_binary_if_provisioning_enabled()  # must not raise


def test_noop_when_binary_found(monkeypatch):
    monkeypatch.setattr(settings, "hermes_provisioning", True)
    monkeypatch.setattr(settings, "hermes_bin", "hermes")
    import shutil

    monkeypatch.setattr(shutil, "which", lambda _bin: "/usr/local/bin/hermes")
    _check_hermes_binary_if_provisioning_enabled()  # must not raise


def test_exits_when_binary_missing(monkeypatch):
    monkeypatch.setattr(settings, "hermes_provisioning", True)
    monkeypatch.setattr(settings, "hermes_bin", "hermes-that-does-not-exist")
    import shutil

    monkeypatch.setattr(shutil, "which", lambda _bin: None)
    with pytest.raises(SystemExit):
        _check_hermes_binary_if_provisioning_enabled()
