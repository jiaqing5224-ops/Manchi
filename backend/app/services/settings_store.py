"""Local JSON-backed application settings store."""

from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


LLM_API_FORMATS = {"openai_chat_completions", "anthropic_messages"}

DEFAULT_SETTINGS: dict[str, Any] = {
    "version": 1,
    "app": {
        "auto_launch": False,
        "minimize_to_tray": True,
    },
    "llm": {
        "api_format": "openai_chat_completions",
        "endpoint": "",
        "api_key": "",
        "model": "",
        "timeout_seconds": 60,
    },
    "mail": {
        "scan_interval": 15,
        "max_mails": 50,
    },
    "system": {},
    "updated_at": None,
}


def get_settings_path() -> Path:
    """Return the user-owned settings.json path."""
    path = _documents_dir() / "Manchi" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_settings() -> dict[str, Any]:
    """Load settings.json, creating it with defaults when missing."""
    path = get_settings_path()
    if not path.exists():
        settings = deepcopy(DEFAULT_SETTINGS)
        settings["updated_at"] = _now_iso()
        _write_settings(path, settings)
        return settings

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"读取 settings.json 失败: {exc}") from exc

    if not isinstance(raw, dict):
        raise RuntimeError("settings.json 顶层必须是 JSON 对象")

    settings = _deep_merge(deepcopy(DEFAULT_SETTINGS), raw)
    settings["llm"]["api_format"] = _normalize_api_format(settings["llm"].get("api_format"))
    return settings


def save_flat_settings(data: dict[str, Any]) -> dict[str, Any]:
    """Save settings from the flat API payload and return the full settings dict."""
    settings = load_settings()

    mapping: dict[str, tuple[str, str]] = {
        "auto_launch": ("app", "auto_launch"),
        "minimize_to_tray": ("app", "minimize_to_tray"),
        "api_format": ("llm", "api_format"),
        "endpoint": ("llm", "endpoint"),
        "api_key": ("llm", "api_key"),
        "model": ("llm", "model"),
        "timeout_seconds": ("llm", "timeout_seconds"),
        "scan_interval": ("mail", "scan_interval"),
        "max_mails": ("mail", "max_mails"),
    }

    for field, value in data.items():
        if field not in mapping:
            continue
        section, key = mapping[field]
        settings.setdefault(section, {})[key] = _coerce_value(field, value)

    settings["llm"]["api_format"] = _normalize_api_format(settings["llm"].get("api_format"))
    settings["updated_at"] = _now_iso()
    _write_settings(get_settings_path(), settings)
    return settings


def to_flat_response(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Convert nested settings.json content to the frontend response shape."""
    settings = settings or load_settings()
    app_settings = settings.get("app", {})
    llm_settings = settings.get("llm", {})
    mail_settings = settings.get("mail", {})
    return {
        "auto_launch": bool(app_settings.get("auto_launch", False)),
        "minimize_to_tray": bool(app_settings.get("minimize_to_tray", True)),
        "api_format": _normalize_api_format(llm_settings.get("api_format")),
        "endpoint": str(llm_settings.get("endpoint") or ""),
        "api_key": str(llm_settings.get("api_key") or ""),
        "model": str(llm_settings.get("model") or ""),
        "timeout_seconds": int(llm_settings.get("timeout_seconds") or 60),
        "scan_interval": int(mail_settings.get("scan_interval") or 15),
        "max_mails": int(mail_settings.get("max_mails") or 50),
        "updated_at": settings.get("updated_at") or _now_iso(),
        "settings_path": str(get_settings_path()),
    }


def get_llm_settings() -> dict[str, Any]:
    """Return the LLM section from settings.json."""
    settings = load_settings()
    llm_settings = settings.get("llm", {})
    return {
        "api_format": _normalize_api_format(llm_settings.get("api_format")),
        "endpoint": str(llm_settings.get("endpoint") or "").strip(),
        "api_key": str(llm_settings.get("api_key") or "").strip(),
        "model": str(llm_settings.get("model") or "").strip(),
        "timeout_seconds": int(llm_settings.get("timeout_seconds") or 60),
    }


def _write_settings(path: Path, settings: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _normalize_api_format(value: Any) -> str:
    api_format = str(value or "openai_chat_completions")
    if api_format not in LLM_API_FORMATS:
        return "openai_chat_completions"
    return api_format


def _coerce_value(field: str, value: Any) -> Any:
    if field in {"auto_launch", "minimize_to_tray"}:
        return bool(value)
    if field in {"scan_interval", "max_mails", "timeout_seconds"}:
        return max(1, int(value or 1))
    if field in {"endpoint", "api_key", "model", "api_format"}:
        return str(value or "").strip()
    return value


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _documents_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents"
    return Path.home() / "Documents"