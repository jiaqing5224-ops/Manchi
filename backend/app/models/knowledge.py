from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class TaskKnowledge(Base):
    """Knowledge precipitation for a single task.

    One-to-one with Task (task_id is unique). Each task may have at most one
    knowledge entry; (re)generating overwrites the previous one. `chain_context`
    stores the full-chain snapshot used to generate `summary` so the entry is
    auditable and can be regenerated later.
    """

    __tablename__ = "task_knowledge"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task_id = Column(Integer, unique=True, index=True, nullable=False)
    summary = Column(Text, default="")            # user-editable precipitation
    chain_context = Column(Text, default="")      # JSON snapshot of the chain
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
