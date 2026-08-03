"""Settings router — GET/PUT for local settings.json configuration."""

from fastapi import APIRouter, HTTPException

from app.schemas.setting import (
    LlmModelsRequest,
    LlmModelsResponse,
    LlmTestResponse,
    SettingResponse,
    SettingUpdate,
)
from app.services.settings_store import load_settings, save_flat_settings, to_flat_response
from app.services.llm.client import list_llm_models, test_llm_connection

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings() -> SettingResponse:
    return SettingResponse(**to_flat_response(load_settings()))


@router.put("")
def update_settings(data: SettingUpdate) -> SettingResponse:
    settings = save_flat_settings(data.model_dump(exclude_unset=True))
    return SettingResponse(**to_flat_response(settings))


@router.post("/test-llm")
def test_llm_settings() -> LlmTestResponse:
    try:
        result = test_llm_connection()
        return LlmTestResponse(**result)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/llm-models")
def llm_models(data: LlmModelsRequest) -> LlmModelsResponse:
    """List models from the provider using endpoint + api_key (no model needed)."""
    result = list_llm_models(
        api_format=data.api_format,
        endpoint=data.endpoint,
        api_key=data.api_key,
    )
    return LlmModelsResponse(**result)
