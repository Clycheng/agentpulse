from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_workspace_id
from app.core.database import Database, get_db
from app.schemas.model_settings import ModelProviderOut, ModelProviderUpdate
from app.services.model_credentials import (
    ModelCredentialValidationError,
    delete_workspace_model_credential,
    provision_workspace_agents,
    put_workspace_model_credential,
    serialize_model_provider,
    validate_deepseek_key,
    validate_model_name,
)

router = APIRouter(prefix="/settings/model-provider", tags=["settings"])


@router.get("", response_model=ModelProviderOut)
def get_model_provider(
    workspace_id: str = Depends(get_workspace_id),
    conn: Database = Depends(get_db),
) -> ModelProviderOut:
    return ModelProviderOut(**serialize_model_provider(conn, workspace_id))


@router.put("", response_model=ModelProviderOut)
async def update_model_provider(
    payload: ModelProviderUpdate,
    workspace_id: str = Depends(get_workspace_id),
    conn: Database = Depends(get_db),
) -> ModelProviderOut:
    try:
        validate_model_name(payload.model)
        await validate_deepseek_key(payload.api_key.strip())
    except ModelCredentialValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    put_workspace_model_credential(
        conn,
        workspace_id=workspace_id,
        api_key=payload.api_key,
        model=payload.model,
    )
    provision_workspace_agents(conn, workspace_id)
    return ModelProviderOut(**serialize_model_provider(conn, workspace_id))


@router.delete("", response_model=ModelProviderOut)
def delete_model_provider(
    workspace_id: str = Depends(get_workspace_id),
    conn: Database = Depends(get_db),
) -> ModelProviderOut:
    delete_workspace_model_credential(conn, workspace_id)
    return ModelProviderOut(**serialize_model_provider(conn, workspace_id))
