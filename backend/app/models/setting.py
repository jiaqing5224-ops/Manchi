from sqlalchemy import Column, Integer, Boolean, String, DateTime
from sqlalchemy.sql import func
from app.database import Base


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, default=1)  # singleton row
    auto_launch = Column(Boolean, default=False)
    minimize_to_tray = Column(Boolean, default=True)
    model = Column(String(64), default="gpt-4o")
    endpoint = Column(String(512), default="")
    scan_interval = Column(Integer, default=15)
    max_mails = Column(Integer, default=50)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())