import os
import sys
from pydantic_settings import BaseSettings
from pathlib import Path


def get_database_path() -> str:
    """Return the database path.

    In development: use backend/data/manchi.db
    In production (PyInstaller): use %LOCALAPPDATA%/Manchi/data/manchi.db
    """
    if getattr(sys, "frozen", False):
        # PyInstaller bundle — use AppData
        appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        db_path = appdata / "Manchi" / "data" / "manchi.db"
    else:
        # Dev mode — use project directory
        db_path = Path(__file__).parent.parent / "data" / "manchi.db"

    db_path.parent.mkdir(parents=True, exist_ok=True)
    return str(db_path)


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Azure OpenAI
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2025-04-01-preview"
    azure_openai_deployment: str = "gpt-4o-2024-11-20"

    # LLM provider selection: azure / itda
    llm_provider: str = "azure"

    # ITDA (Siemens internal LLM gateway)
    itda_base_url: str = ""
    itda_api_key: str = ""
    itda_model: str = ""

    # Database
    database_path: str = get_database_path()

    # CORS
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:4173",
        "file://",
    ]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
