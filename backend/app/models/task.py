from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    priority = Column(String(16), default="medium")  # high / medium / low
    status = Column(String(32), default="todo")  # todo / in_progress / done
    # Source tracking — every task originates from one of: mail / text / file.
    # Legacy rows only have source_mail_id; source_type is nullable so we can
    # infer "mail" when source_mail_id is present but source_type is NULL.
    source_type = Column(String(16), nullable=True)  # mail / text / file
    source_mail_id = Column(String(255), nullable=True)
    source_text = Column(Text, nullable=True)
    source_file_path = Column(String(512), nullable=True)
    group_id = Column(Integer, nullable=True)  # NULL = ungrouped; refs task_groups.id (done column only)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
