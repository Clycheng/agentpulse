"""UpgradeService (TD-06-T2) — grant an employee a new capability on approval.

North star §1.4: an employee that hits a "I have the task but not the tool" gap
doesn't just fail — it submits a capability-upgrade request (an approval of
type ``capability_upgrade``). When the owner approves (confirming/adjusting the
capability key), this service resolves the capability bundle from the catalog,
installs it onto the employee's Hermes profile via ``ProfileProvisioner``, and
records it in ``agent_capabilities`` so the employee keeps the ability for future
runs.

If the capability needs credentials the employee doesn't have yet, the row is
recorded as ``credential_missing`` (the existing credentials flow then asks the
owner for them) rather than ``enabled``.
"""

from __future__ import annotations

import json

from app.core.database import Database
from app.orchestration.capability_catalog import resolve_bundle
from app.services.workspace import new_id, now_iso


class UpgradeError(ValueError):
    """Raised when an upgrade can't be applied (unknown key / no profile)."""


def _agent_profile(conn: Database, agent_id: str) -> str | None:
    row = conn.execute(
        "SELECT hermes_profile FROM agent_specs WHERE agent_id = ?", (agent_id,)
    ).fetchone()
    return row["hermes_profile"] if row and row["hermes_profile"] else None


def _upsert_capability(
    conn: Database,
    *,
    agent_id: str,
    workspace_id: str,
    capability_key: str,
    bundle: dict,
    status: str,
) -> None:
    """Insert or update the agent_capabilities row (UNIQUE agent_id+key)."""
    existing = conn.execute(
        "SELECT id FROM agent_capabilities WHERE agent_id = ? AND capability_key = ?",
        (agent_id, capability_key),
    ).fetchone()
    now = now_iso()
    fields = (
        json.dumps(bundle.get("skills", []), ensure_ascii=False),
        json.dumps(bundle.get("toolsets", []), ensure_ascii=False),
        json.dumps(bundle.get("mcp", []), ensure_ascii=False),
        json.dumps(bundle.get("required_credentials", []), ensure_ascii=False),
        bundle.get("risk_gate", "auto"),
        status,
        now,
    )
    if existing:
        conn.execute(
            """UPDATE agent_capabilities SET
                 skill_refs_json = ?, toolset_refs_json = ?, mcp_refs_json = ?,
                 required_credentials_json = ?, risk_gate = ?, status = ?, updated_at = ?
               WHERE id = ?""",
            (*fields, existing["id"]),
        )
    else:
        conn.execute(
            """INSERT INTO agent_capabilities
                 (id, agent_id, workspace_id, capability_key, skill_refs_json,
                  toolset_refs_json, mcp_refs_json, required_credentials_json,
                  risk_gate, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_id("cap"), agent_id, workspace_id, capability_key,
                json.dumps(bundle.get("skills", []), ensure_ascii=False),
                json.dumps(bundle.get("toolsets", []), ensure_ascii=False),
                json.dumps(bundle.get("mcp", []), ensure_ascii=False),
                json.dumps(bundle.get("required_credentials", []), ensure_ascii=False),
                bundle.get("risk_gate", "auto"),
                status,
                now, now,
            ),
        )


def execute_upgrade(
    conn: Database,
    *,
    approval: dict,
    approved_capability_key: str,
    provisioner,
) -> dict:
    """Install ``approved_capability_key`` onto the approval's employee.

    Resolves the catalog bundle, installs it via the provisioner, and records an
    ``agent_capabilities`` row (``credential_missing`` if the bundle needs creds
    the employee lacks, else ``enabled``). Returns a summary dict. Caller commits.
    """
    agent_id = approval["agent_id"]
    workspace_id = approval["workspace_id"]
    if not agent_id:
        raise UpgradeError("approval has no agent to upgrade")
    if not approved_capability_key:
        raise UpgradeError("no capability key approved")

    try:
        bundle = resolve_bundle([approved_capability_key])  # validates the key
    except ValueError as exc:
        raise UpgradeError(str(exc)) from exc

    profile = _agent_profile(conn, agent_id)
    if not profile:
        raise UpgradeError("employee has no provisioned Hermes profile")

    provisioner.add_capability(profile, approved_capability_key, bundle)

    # If the capability needs credentials, mark it credential_missing so the
    # existing credentials flow can ask the owner; otherwise it's live.
    status = "credential_missing" if bundle.get("required_credentials") else "enabled"
    _upsert_capability(
        conn,
        agent_id=agent_id,
        workspace_id=workspace_id,
        capability_key=approved_capability_key,
        bundle=bundle,
        status=status,
    )
    return {
        "capability_key": approved_capability_key,
        "status": status,
        "profile": profile,
        "required_credentials": bundle.get("required_credentials", []),
    }
