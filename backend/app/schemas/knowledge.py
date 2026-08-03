from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class KnowledgeCreate(BaseModel):
    task_id: int
    summary: str
    chain_context: Optional[str] = None  # full-chain JSON snapshot (from /draft)


class KnowledgeUpdate(BaseModel):
    summary: str


class KnowledgeResponse(BaseModel):
    id: int
    task_id: int
    summary: str
    created_at: datetime
    updated_at: datetime
    # Display-only fields joined from the linked task (avoid a second request
    # when rendering the knowledge-base list).
    task_title: str = ""
    priority: Optional[str] = None
    status: Optional[str] = None
    source_type: Optional[str] = None
    source_mail_id: Optional[str] = None

    model_config = {"from_attributes": True}
