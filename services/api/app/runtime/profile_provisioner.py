"""Profile provisioner abstraction (TD-04-T2).

Abstracts the physical Hermes profile operations so that:
- RecordOnlyProvisioner: v1/tests — records actions without side effects
- LocalHermesProvisioner: T6 — real Hermes CLI calls (requires agentpulse session)

See TD-04 for design details.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
