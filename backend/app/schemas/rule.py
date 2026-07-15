"""Rule schemas — typed pipeline configuration for the orchestrator."""

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


# ---- Source config (discriminated by "type") ----

class MailSourceConfig(BaseModel):
    type: str = "mail"
    days_range: int = Field(5, ge=1, le=90, description="扫描最近 N 天的邮件")
    sender_filter: str = Field("", description="按发件人过滤（模糊匹配，空=不过滤）")

class TextSourceConfig(BaseModel):
    type: str = "text"
    content: str = Field("", description="自定义文本内容")

class FileSourceConfig(BaseModel):
    type: str = "file"
    file_path: str = Field("", description="本地文件路径")
    encoding: str = Field("utf-8", description="文件编码")


# ---- Trigger config ----

class ManualTriggerConfig(BaseModel):
    type: str = "manual"

class ScheduleTriggerConfig(BaseModel):
    type: str = "schedule"
    cron: str = Field("0 9 * * *", description="cron 表达式（5 段：分 时 日 月 周）")
    description: str = Field("", description="cron 的中文释义，供前端展示")

class NewMailTriggerConfig(BaseModel):
    type: str = "new_mail"


# ---- Action config ----

class ActionConfig(BaseModel):
    """A single action in the action chain."""
    type: str = Field(..., description="动作类型：ai_extract/ai_summarize/ai_classify/export_excel/export_json/notify")
    params: dict[str, Any] = Field(default_factory=dict, description="动作参数")


# ---- CRUD schemas ----

class RuleCreate(BaseModel):
    name: str
    description: str = ""
    source_config: dict[str, Any] = Field(default_factory=lambda: {"type": "text", "content": ""})
    trigger_config: dict[str, Any] = Field(default_factory=lambda: {"type": "manual"})
    actions_config: list[dict[str, Any]] = Field(default_factory=list)
    is_active: bool = True


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    source_config: Optional[dict[str, Any]] = None
    trigger_config: Optional[dict[str, Any]] = None
    actions_config: Optional[list[dict[str, Any]]] = None
    is_active: Optional[bool] = None


class RuleResponse(BaseModel):
    id: int
    name: str
    description: str
    source_config: dict[str, Any]
    trigger_config: dict[str, Any]
    actions_config: list[dict[str, Any]]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None
    last_run_message: Optional[str] = None

    model_config = {"from_attributes": True}


class RuleRunResult(BaseModel):
    """Result of running a rule pipeline."""
    rule_id: int
    status: str  # success / failed
    message: str = ""
    artifacts: list[str] = Field(default_factory=list, description="产物文件绝对路径列表")
    steps: list[str] = Field(default_factory=list, description="执行步骤摘要")
    started_at: datetime
    finished_at: datetime


class ArtifactItem(BaseModel):
    name: str
    path: str
    size: int
    modified: str
