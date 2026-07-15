from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from app.database import Base


class Rule(Base):
    """Automation rule — a pipeline of source → trigger → actions[]."""

    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")

    # Pipeline configuration (three structured JSON blocks).
    # source_config:   {"type":"mail|text|file", ...type-specific params}
    # trigger_config:  {"type":"manual|schedule|new_mail", ...type-specific params}
    # actions_config:  [{"type":"ai_extract","params":{...}}, ...]
    source_config = Column(JSON, default=dict)
    trigger_config = Column(JSON, default=dict)
    actions_config = Column(JSON, default=list)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_run_at = Column(DateTime, nullable=True)
    last_run_status = Column(String(32), nullable=True)  # success / failed / running
    last_run_message = Column(Text, nullable=True)
