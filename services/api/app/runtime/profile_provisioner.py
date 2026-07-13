"""Profile provisioner abstraction (TD-04-T2).

Abstracts the physical Hermes profile operations so that:
- RecordOnlyProvisioner: v1/tests — records actions without side effects
- LocalHermesProvisioner: T6 — real Hermes CLI calls (requires agentpulse session)

See TD-04 for design details.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class ProvisioningAction:
    """Record of a single provisioning action (for audit/testing)."""

    action: str
    profile_name: str
    details: dict = field(default_factory=dict)


class ProfileProvisioner(Protocol):
    """Abstract interface for provisioning Hermes profiles.

    Implementations:
    - RecordOnlyProvisioner: records actions, no side effects (v1/tests)
    - LocalHermesProvisioner: real Hermes CLI (TD-04-T6, needs agentpulse session)
    """

    def create_profile(self, profile_name: str) -> None:
        """Create a new Hermes profile (hermes profile create)."""
        ...

    def write_soul(self, profile_name: str, soul_md: str) -> None:
        """Write SOUL.md to the profile directory."""
        ...

    def configure(
        self,
        profile_name: str,
        *,
        model: str,
        toolsets: list[str],
        mcp: list[str],
    ) -> None:
        """Configure profile model, toolsets, and MCP servers."""
        ...

    def install_skills(self, profile_name: str, skills: list[str]) -> None:
        """Install skills into the profile."""
        ...

    def write_credentials(
        self, profile_name: str, creds: dict[str, str]
    ) -> None:
        """Write credentials to profile's .env file.

        SECURITY: credential values must NEVER appear in logs or responses.
        """
        ...


class RecordOnlyProvisioner:
    """Provisioner that records all actions without side effects.

    Used in v1 and tests. Allows asserting on the call sequence without
    actually touching the filesystem or running Hermes CLI.
    """

    def __init__(self) -> None:
        self.actions: list[ProvisioningAction] = []

    def create_profile(self, profile_name: str) -> None:
        self.actions.append(
            ProvisioningAction(
                action="create_profile",
                profile_name=profile_name,
            )
        )

    def write_soul(self, profile_name: str, soul_md: str) -> None:
        self.actions.append(
            ProvisioningAction(
                action="write_soul",
                profile_name=profile_name,
                details={"soul_length": len(soul_md)},
            )
        )

    def configure(
        self,
        profile_name: str,
        *,
        model: str,
        toolsets: list[str],
        mcp: list[str],
    ) -> None:
        self.actions.append(
            ProvisioningAction(
                action="configure",
                profile_name=profile_name,
                details={
                    "model": model,
                    "toolsets": list(toolsets),
                    "mcp": list(mcp),
                },
            )
        )

    def install_skills(self, profile_name: str, skills: list[str]) -> None:
        self.actions.append(
            ProvisioningAction(
                action="install_skills",
                profile_name=profile_name,
                details={"skills": list(skills)},
            )
        )

    def write_credentials(
        self, profile_name: str, creds: dict[str, str]
    ) -> None:
        # SECURITY: do NOT record credential values, only key names
        self.actions.append(
            ProvisioningAction(
                action="write_credentials",
                profile_name=profile_name,
                details={"credential_keys": sorted(creds.keys())},
            )
        )

    def get_actions(self) -> list[ProvisioningAction]:
        """Return recorded actions (for test assertions)."""
        return list(self.actions)

    def clear(self) -> None:
        """Clear recorded actions."""
        self.actions.clear()


class HermesProvisionError(RuntimeError):
    """Raised when a `hermes` CLI provisioning command fails."""


class LocalHermesProvisioner:
    """Real provisioner — drives the `hermes` CLI to create + configure profiles.

    Verified against Hermes Agent v0.18.2 (2026-07) with these exact commands:
      - hermes profile create <name> --no-alias --no-skills
      - hermes --profile <name> config set model <provider/model>
      - hermes --profile <name> config set terminal.working_dir <ABS>
      - hermes --profile <name> tools enable <toolset...>
      - hermes --profile <name> skills install <id> --yes
      - credentials appended to <profile>/.env (path via `config env-path`)

    ADR 0005: every profile's terminal.working_dir is forced to an absolute path
    under ``work_root`` so an agent's file/tool activity can never escape into an
    unrelated repo. ``--no-alias`` avoids writing wrapper scripts into
    ~/.local/bin (the import-wrapper pitfall noted in the Hermes facts).

    Must run in an agentpulse-anchored session (never inside UnitPulse).
    """

    def __init__(
        self,
        *,
        work_root: str,
        hermes_bin: str = "hermes",
        default_model: str = "deepseek/deepseek-v4-flash",
        timeout: int = 120,
    ) -> None:
        if not os.path.isabs(work_root):
            raise HermesProvisionError(
                f"work_root must be an absolute path (ADR 0005): {work_root!r}"
            )
        self.work_root = work_root
        self.hermes_bin = hermes_bin
        self.default_model = default_model
        self.timeout = timeout

    def _run(self, args: list[str], *, profile: str | None = None) -> str:
        cmd = [self.hermes_bin]
        if profile:
            cmd += ["--profile", profile]
        cmd += args
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout
            )
        except FileNotFoundError as exc:
            raise HermesProvisionError(
                f"`{self.hermes_bin}` not found on PATH"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise HermesProvisionError(f"`{' '.join(cmd)}` timed out") from exc
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise HermesProvisionError(f"`{' '.join(cmd)}` failed: {detail}")
        return proc.stdout

    def _profile_dir(self, profile_name: str) -> Path:
        env_path = self._run(["config", "env-path"], profile=profile_name).strip()
        return Path(env_path).parent

    def _profile_exists(self, profile_name: str) -> bool:
        listing = self._run(["profile", "list"])
        # Names appear as bare tokens (the default profile is prefixed with ◆).
        tokens = listing.replace("◆", " ").split()
        return profile_name in tokens

    # --- ProfileProvisioner protocol ---

    def create_profile(self, profile_name: str) -> None:
        if self._profile_exists(profile_name):
            return  # idempotent
        self._run(
            ["profile", "create", profile_name, "--no-alias", "--no-skills"]
        )

    def write_soul(self, profile_name: str, soul_md: str) -> None:
        (self._profile_dir(profile_name) / "SOUL.md").write_text(
            soul_md, encoding="utf-8"
        )

    def configure(
        self,
        profile_name: str,
        *,
        model: str,
        toolsets: list[str],
        mcp: list[str],
    ) -> None:
        self._run(
            ["config", "set", "model", model or self.default_model],
            profile=profile_name,
        )
        # ADR 0005: bind an absolute, per-profile work dir; create it up front.
        workdir = os.path.join(self.work_root, profile_name, "work")
        os.makedirs(workdir, exist_ok=True)
        self._run(
            ["config", "set", "terminal.working_dir", workdir],
            profile=profile_name,
        )
        if toolsets:
            self._run(["tools", "enable", *toolsets], profile=profile_name)
        # NOTE: real MCP servers need endpoints/auth (`hermes mcp add ...`); the
        # catalog only carries logical names, so MCP wiring is deferred until a
        # channel/tool endpoint exists. Left intentionally unhandled here.

    def install_skills(self, profile_name: str, skills: list[str]) -> None:
        for skill in skills:
            self._run(["skills", "install", skill, "--yes"], profile=profile_name)

    def write_credentials(
        self, profile_name: str, creds: dict[str, str]
    ) -> None:
        # SECURITY: values are written only to the profile's gitignored .env,
        # never logged or returned.
        env_path = self._profile_dir(profile_name) / ".env"
        with env_path.open("a", encoding="utf-8") as handle:
            for key, value in creds.items():
                handle.write(f"{key}={value}\n")

    def delete_profile(self, profile_name: str) -> None:
        """Tear down a profile (employee removed). Best-effort."""
        if self._profile_exists(profile_name):
            self._run(["profile", "delete", profile_name, "--yes"])


def build_provisioner_from_settings() -> ProfileProvisioner:
    """Pick the provisioner from config: LocalHermes when hermes_provisioning is
    on (real `hermes` CLI), else RecordOnly (tests / non-Hermes envs)."""
    from app.core.config import settings

    if settings.hermes_provisioning:
        work_root = os.path.abspath(settings.hermes_work_root or ".hermes-data")
        return LocalHermesProvisioner(work_root=work_root, hermes_bin=settings.hermes_bin)
    return RecordOnlyProvisioner()
