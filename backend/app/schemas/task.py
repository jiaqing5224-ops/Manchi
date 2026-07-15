from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    status: str = "todo"
    source_type: Optional[str] = None  # mail / text / file
    source_mail_id: Optional[str] = None
    source_text: Optional[str] = None
    source_file_path: Optional[str] = None
    group_id: Optional[int] = None
    due_date: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    source_type: Optional[str] = None
    source_mail_id: Optional[str] = None
    source_text: Optional[str] = None
    source_file_path: Optional[str] = None
    group_id: Optional[int] = None
    due_date: Optional[str] = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str
    priority: str
    status: str
    source_type: Optional[str] = None
    source_mail_id: Optional[str] = None
    source_text: Optional[str] = None
    source_file_path: Optional[str] = None
    group_id: Optional[int] = None
    due_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
