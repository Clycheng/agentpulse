"""Read-only capability / role-bundle catalog endpoints (TD-07-T2 API half).

These power the desktop "hire by role" flow: the client lists preset roles and,
on selection, pre-fills the capability checklist (still editable) before calling
POST /api/agents.
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_workspace_id
from app.orchestration import (
    get_role_bundle,
    list_role_bundles,
    resolve_bundle,
)
from app.schemas.agent_spec import ResolvedBundleOut, RoleBundleOut

router = APIRouter(tags=["catalog"])


@router.get("/role-bundles", response_model=list[RoleBundleOut])
def list_role_bundles_route(
    _: str = Depends(get_workspace_id),  # require an authenticated workspace
) -> list[RoleBundleOut]:
    bundles: list[RoleBundleOut] = []
    for name in list_role_bundles():
        keys = get_role_bundle(name)
        bundles.append(
            RoleBundleOut(
                role_name=name,
                capability_keys=keys,
                resolved=ResolvedBundleOut(**resolve_bundle(keys)),
            )
        )
    return bundles
