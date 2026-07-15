from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TaskGroupCreate(BaseModel):
    name: str


class TaskGroupUpdate(BaseModel):
    name: Optional[str] = None


class TaskGroupResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
