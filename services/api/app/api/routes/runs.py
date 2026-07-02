from fastapi import APIRouter, HTTPException

from app.runtime.deepseek import (
    DeepSeekAPIError,
    DeepSeekChatClient,
    DeepSeekNotConfigured,
)
from app.schemas.run import LlmChatRequest, LlmChatResponse

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("/llm-chat", response_model=LlmChatResponse)
async def run_llm_chat(payload: LlmChatRequest) -> LlmChatResponse:
    try:
        return await DeepSeekChatClient().complete(payload)
    except DeepSeekNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DeepSeekAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
