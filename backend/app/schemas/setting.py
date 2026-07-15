from typing import Literal, Optional

from pydantic import BaseModel


ApiFormat = Literal["openai_chat_completions", "anthropic_messages"]


class SettingResponse(BaseModel):
    auto_launch: bool
    minimize_to_tray: bool
    api_format: ApiFormat
    model: str
    endpoint: str
    api_key: str
    timeout_seconds: int
    scan_interval: int
    max_mails: int
    updated_at: str
    settings_path: str


class SettingUpdate(BaseModel):
    auto_launch: Optional[bool] = None
    minimize_to_tray: Optional[bool] = None
    api_format: Optional[ApiFormat] = None
    model: Optional[str] = None
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    timeout_seconds: Optional[int] = None
    scan_interval: Optional[int] = None
    max_mails: Optional[int] = None


class LlmTestResponse(BaseModel):
    ok: bool
    api_format: ApiFormat
    model: str
    message: str
    response_preview: str = ""