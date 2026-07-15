from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class MailResponse(BaseModel):
    id: str
    subject: str
    sender_name: str
    sender_email: str
    body_preview: str
    received_at: Optional[datetime] = None
    is_read: bool
    is_processed: bool

    model_config = {"from_attributes": True}


class AnalyzeResult(BaseModel):
    mail_id: str
    tasks: list["AiTaskSchema"]


class AiTaskSchema(BaseModel):
    title: str
    description: str
    priority: str
