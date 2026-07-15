"""Settings router — GET/PUT for local settings.json configuration."""

from fastapi import APIRouter, HTTPException

from app.schemas.setting import LlmTestResponse, SettingResponse, SettingUpdate
from app.services.settings_store import load_settings, save_flat_settings, to_flat_response
from app.services.llm.client import test_llm_connection

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
