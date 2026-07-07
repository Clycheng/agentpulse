"""Orchestration layer for group discussion protocol.

This module implements the core orchestration logic for AgentPulse:
- Discussion state machine (discussing -> aligned)
- Consensus brief management
- Task creation gate (must have confirmed brief)
- Capability catalog (system-level static asset)

See ADR 0006 for design details.
"""

from app.orchestration.brief import (
    create_brief,
    confirm_brief,
    reject_brief,
    get_brief_by_id,
    serialize_brief,
)
from app.orchestration.capability_catalog import (
    CATALOG,
    CapabilityDef,
    get_capability,
    resolve_bundle,
    validate_capability_keys,
)
from app.orchestration.discussion import (
    DiscussionStatus,
    get_discussion_status,
    set_discussion_status,
)
from app.orchestration.gate import (
    validate_task_creation_gate,
    TaskCreationGateError,
)

__all__ = [
    "create_brief",
    "confirm_brief",
    "reject_brief",
    "get_brief_by_id",
    "serialize_brief",
    "DiscussionStatus",
    "get_discussion_status",
    "set_discussion_status",
    "validate_task_creation_gate",
    "TaskCreationGateError",
    "CATALOG",
    "CapabilityDef",
    "get_capability",
    "resolve_bundle",
    "validate_capability_keys",
]