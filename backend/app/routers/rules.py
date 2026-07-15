"""Rules router — CRUD + pipeline run + artifact management."""

import os
import sys
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.rule import Rule
from app.schemas.rule import (
    RuleCreate,
    RuleUpdate,
    RuleResponse,
    RuleRunResult,
    ArtifactItem,
)
from app.services.orchestrator.engine import PipelineExecutor, get_rule_artifacts_dir

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("")
def list_rules(db: Session = Depends(get_db)) -> list[RuleResponse]:
    rules = db.query(Rule).order_by(Rule.created_at.desc()).all()
    return [RuleResponse.model_validate(r) for r in rules]


@router.post("", status_code=201)
def create_rule(data: RuleCreate, db: Session = Depends(get_db)) -> RuleResponse:
    rule = Rule(**data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return RuleResponse.model_validate(rule)


@router.put("/{rule_id}")
def update_rule(rule_id: int, data: RuleUpdate, db: Session = Depends(get_db)) -> RuleResponse:
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "Rule not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return RuleResponse.model_validate(rule)


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "Rule not found")
    db.delete(rule)
    db.commit()
    return {"ok": True}


@router.post("/{rule_id}/run")
def run_rule(rule_id: int, db: Session = Depends(get_db)) -> RuleRunResult:
    """Execute the rule's pipeline immediately and return the result."""
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "Rule not found")
    if not rule.is_active:
        raise HTTPException(400, "规则已暂停，无法运行")
    try:
        result = PipelineExecutor(db).run(rule_id)
        return RuleRunResult(
            rule_id=result["rule_id"],
            status=result["status"],
            message=result["message"],
            artifacts=result["artifacts"],
            steps=result["steps"],
            started_at=datetime.fromisoformat(result["started_at"]),
            finished_at=datetime.fromisoformat(result["finished_at"]),
        )
    except Exception as e:
        raise HTTPException(500, f"Pipeline execution failed: {e}")


@router.get("/{rule_id}/artifacts")
def list_artifacts(rule_id: int, db: Session = Depends(get_db)) -> list[ArtifactItem]:
    """List artifact files in the rule's dedicated subdirectory."""
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "Rule not found")
    art_dir = Path(get_rule_artifacts_dir(rule.id, rule.name))
    if not art_dir.is_dir():
        return []
    items: list[ArtifactItem] = []
    for f in sorted(art_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file():
            st = f.stat()
            items.append(ArtifactItem(
                name=f.name,
                path=str(f),
                size=st.st_size,
                modified=datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            ))
    return items


@router.post("/{rule_id}/open-artifacts")
def open_artifacts(rule_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    """Open the rule's artifacts directory in the OS file explorer."""
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "Rule not found")
    path = get_rule_artifacts_dir(rule.id, rule.name)
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            import subprocess
            subprocess.run(["open", path], check=False)
        else:
            import subprocess
            subprocess.run(["xdg-open", path], check=False)
        return {"ok": True, "path": path}
    except Exception as e:
        raise HTTPException(500, f"Open artifacts dir failed: {e}")


# ---- Templates ----

RULE_TEMPLATES: list[dict[str, object]] = [
    # ---- 闭环演示系列（突出多能力组合） ----
    {
        "key": "meeting_to_task",
        "name": "会议雷达 → Excel + 任务",
        "description": "扫描本周会议邮件，AI 提取会议时间/主题，导出 Excel 并自动在任务中心创建会议准备任务",
        "source_config": {"type": "mail", "days_range": 7, "sender_filter": ""},
        "trigger_config": {"type": "manual"},
        "actions_config": [
            {"type": "ai_meeting_extract", "params": {}},
            {"type": "export_excel", "params": {"columns": ["subject", "start_time", "end_time", "duration_hours"], "filename": "会议报告.xlsx"}},
            {"type": "create_task", "params": {"title_field": "subject", "priority": "high"}},
        ],
    },
    {
        "key": "mail_analysis_report",
        "name": "邮件智能分析 → Markdown 报告",
        "description": "对近期邮件进行分类（紧急/常规/通知/垃圾）并生成整体摘要，输出 Markdown 分析报告",
        "source_config": {"type": "mail", "days_range": 3, "sender_filter": ""},
        "trigger_config": {"type": "manual"},
        "actions_config": [
            {"type": "ai_classify", "params": {"categories": ["紧急", "常规", "通知", "垃圾"]}},
            {"type": "ai_summarize", "params": {"max_length": 300}},
            {"type": "export_markdown", "params": {"filename": "邮件分析报告.md", "title": "邮件智能分析报告"}},
        ],
    },
    {
        "key": "urgent_mail_task",
        "name": "紧急邮件 → 任务 + 通知",
        "description": "识别近期紧急邮件，提取待办事项，自动创建高优先级任务并通知",
        "source_config": {"type": "mail", "days_range": 2, "sender_filter": ""},
        "trigger_config": {"type": "manual"},
        "actions_config": [
            {"type": "ai_classify", "params": {"categories": ["紧急", "常规"]}},
            {"type": "ai_extract", "params": {"fields": ["action_item", "deadline"], "prompt_extra": "从紧急邮件中提取需要立即处理的待办事项和截止时间"}},
            {"type": "create_task", "params": {"title_field": "action_item", "priority": "high"}},
            {"type": "notify", "params": {"message": "已自动创建紧急任务，请前往任务中心查看"}},
        ],
    },
    {
        "key": "text_to_task",
        "name": "文本智能分析 → Excel + 任务（非邮件源）",
        "description": "对自定义文本进行分类与摘要，导出 Excel 并创建跟进任务，展示非邮件源的闭环能力",
        "source_config": {"type": "text", "content": "粘贴要分析的文本，例如项目周报、会议纪要、需求清单等"},
        "trigger_config": {"type": "manual"},
        "actions_config": [
            {"type": "ai_classify", "params": {"categories": ["进度风险", "资源问题", "里程碑", "其他"]}},
            {"type": "ai_summarize", "params": {"max_length": 200}},
            {"type": "export_excel", "params": {"filename": "文本分析.xlsx"}},
            {"type": "create_task", "params": {"title_field": "tag", "priority": "medium"}},
        ],
    },
    # ---- 基础能力模板（单一能力演示） ----
    {
        "key": "meeting_scan",
        "name": "会议邮件扫描 → Excel",
        "description": "扫描本周会议邮件，AI 提取会议时间/主题/时长，汇总为 Excel",
        "source_config": {"type": "mail", "days_range": 7, "sender_filter": ""},
        "trigger_config": {"type": "manual"},
        "actions_config": [
            {"type": "ai_meeting_extract", "params": {}},
            {"type": "export_excel", "params": {"columns": ["subject", "start_time", "end_time", "duration_hours"], "filename": "会议报告.xlsx"}},
        ],
    },
    {
        "key": "mail_classify",
        "name": "邮件自动分类 → JSON",
        "description": "对近期邮件按紧急/常规/垃圾分类，结果导出 JSON",
        "source_config": {"type": "mail", "days_range": 3, "sender_filter": ""},
        "trigger_config": {"type": "manual"},
        "actions_config": [
            {"type": "ai_classify", "params": {"categories": ["紧急", "常规", "垃圾"]}},
            {"type": "export_json", "params": {"filename": "邮件分类结果.json"}},
        ],
    },
    {
        "key": "text_summarize",
        "name": "文本摘要 → JSON",
        "description": "对自定义文本生成中文摘要并导出",
        "source_config": {"type": "text", "content": ""},
        "trigger_config": {"type": "manual"},
        "actions_config": [
            {"type": "ai_summarize", "params": {"max_length": 300}},
            {"type": "export_json", "params": {"filename": "摘要.json"}},
        ],
    },
    {
        "key": "file_translate",
        "name": "文档翻译 → JSON",
        "description": "读取本地文件并翻译为中文，导出 JSON",
        "source_config": {"type": "file", "file_path": "", "encoding": "utf-8"},
        "trigger_config": {"type": "manual"},
        "actions_config": [
            {"type": "ai_extract", "params": {"fields": ["translated_text"], "prompt_extra": "将原文翻译为中文，translated_text 字段放完整译文。"}},
            {"type": "export_json", "params": {"filename": "译文.json"}},
        ],
    },
    {
        "key": "workload_excel_export",
        "name": "自动拉取本周工时",
        "description": "读取开发资源管理 Excel，过滤 Cheng Jia Qing 的本周工时，导出为工时记录.xlsx",
        "source_config": {"type": "text", "content": ""},
        "trigger_config": {"type": "manual"},
        "actions_config": [
            {"type": "excel_workload_export", "params": {
                "file_path": "C:\\Users\\YOUR_USERNAME\\OneDrive - Siemens AG\\GBS CN FPS RPM - 10 - RPM Common Topics\\开发资源管理.xlsx",
                "sheet_name": "周计划主表",
                "name_filter": "Cheng Jia Qing",
                "output_filename": "工时记录.xlsx"
            }}
        ],
    },
]


@router.get("/templates/list")
def list_templates() -> list[dict[str, object]]:
    """Return built-in rule templates for the create-from-template UI."""
    return RULE_TEMPLATES
