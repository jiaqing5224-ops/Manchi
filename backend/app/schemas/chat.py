from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    history: list[dict] = []


class ChatChunk(BaseModel):
    text: str
    done: bool = False
