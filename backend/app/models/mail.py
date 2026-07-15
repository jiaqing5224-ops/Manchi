from sqlalchemy import Column, String, Text, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base


class Mail(Base):
    __tablename__ = "mails"

    id = Column(String(255), primary_key=True)  # Outlook EntryID
    subject = Column(String(255), default="")
    sender_name = Column(String(128), default="")
    sender_email = Column(String(255), default="")
    body_preview = Column(Text, default="")
    received_at = Column(DateTime, nullable=True)
    is_read = Column(Boolean, default=False)
    is_processed = Column(Boolean, default=False)  # analyzed by AI
    created_at = Column(DateTime, server_default=func.now())
