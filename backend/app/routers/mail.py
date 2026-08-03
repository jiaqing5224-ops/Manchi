"""
Mail router — scan Outlook, list cached mails, AI analysis.
"""

import json
import logging
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.mail import Mail
from app.models.task import Task
from app.schemas.mail import MailResponse, AnalyzeResult, AiTaskSchema
from app.services.outlook.mail_handler import scan_inbox, open_mail_in_outlook
from app.services.llm.client import chat_complete
from app.services.llm.prompts import MAIL_ANALYSIS_PROMPT
from app.services.task_service import create_task
from app.schemas.task import TaskCreate
from app.services.settings_store import load_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mail", tags=["mail"])


@router.post("/scan")
def scan_mails(db: Session = Depends(get_db)):
    """Scan Outlook inbox, cache new mails, and generate tasks for them."""
    try:
        try:
            max_mails = int(load_settings().get("mail", {}).get("max_mails", 5) or 5)
        except Exception:
            max_mails = 5
        mails = scan_inbox(max_items=max_mails)
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    count = 0
    tasks_count = 0
    failed_count = 0
    last_error = None
    for m in mails:
        existing = db.query(Mail).filter(Mail.id == m.entry_id).first()
        if existing:
            if not existing.is_processed:
                try:
                    tasks_count += _create_missing_tasks_for_scan(db, existing)
                except Exception as e:
                    db.rollback()
                    failed_count += 1
                    last_error = str(e)
                    logger.exception("扫描时分析已存在邮件失败 subject=%s", m.subject)
            continue
        mail = Mail(
            id=m.entry_id,
            subject=m.subject,
            sender_name=m.sender_name,
            sender_email=m.sender_email,
            body_preview=m.body_preview,
            received_at=m.received_at,
        )
        db.add(mail)
        db.commit()
        count += 1

        try:
            tasks_count += _create_missing_tasks_for_scan(db, mail)
        except Exception as e:
            db.rollback()
            failed_count += 1
            last_error = str(e)
            logger.exception("扫描时分析新邮件失败 subject=%s", m.subject)
    return {
        "scanned": count,
        "total": len(mails),
        "tasks_created": tasks_count,
        "analysis_failed": failed_count,
        "last_error": last_error,
    }


@router.get("")
def list_mails(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """List cached mails, most recent first, with their AI-generated tasks."""
    mails = (
        db.query(Mail)
        .order_by(Mail.received_at.desc().nullslast())
        .offset(skip)
        .limit(limit)
        .all()
    )
    tasks_by_mail = _tasks_by_mail(db, [m.id for m in mails])
    result = []
    for m in mails:
        resp = MailResponse.model_validate(m)
        resp.tasks = tasks_by_mail.get(m.id, [])
        result.append(resp)
    return result


@router.get("/{mail_id}")
def get_mail(mail_id: str, db: Session = Depends(get_db)):
    """Get a single mail by ID, with its AI-generated tasks."""
    mail = db.query(Mail).filter(Mail.id == mail_id).first()
    if not mail:
        raise HTTPException(404, "Mail not found")
    resp = MailResponse.model_validate(mail)
    resp.tasks = _tasks_by_mail(db, [mail_id]).get(mail_id, [])
    return resp


@router.post("/{mail_id}/open")
def open_mail(mail_id: str, db: Session = Depends(get_db)):
    """Open the original mail in the user's Outlook client (jump to source)."""
    mail = db.query(Mail).filter(Mail.id == mail_id).first()
    if not mail:
        raise HTTPException(404, "Mail not found")
    try:
        open_mail_in_outlook(mail_id)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    return {"ok": True}


@router.post("/{mail_id}/analyze")
def analyze_mail(mail_id: str, db: Session = Depends(get_db)):
    """AI-analyze a mail and generate tasks."""
    mail = db.query(Mail).filter(Mail.id == mail_id).first()
    if not mail:
        raise HTTPException(404, "Mail not found")

    try:
        created = _analyze_mail_to_tasks(db, mail)
    except Exception as e:
        raise HTTPException(500, f"AI analysis failed: {e}")

    return AnalyzeResult(mail_id=mail_id, tasks=created)


def _create_missing_tasks_for_scan(db: Session, mail: Mail) -> int:
    before_count = db.query(Task).filter(Task.source_mail_id == mail.id).count()
    _analyze_mail_to_tasks(db, mail)
    after_count = db.query(Task).filter(Task.source_mail_id == mail.id).count()
    return max(0, after_count - before_count)


def _analyze_mail_to_tasks(db: Session, mail: Mail) -> list[AiTaskSchema]:
    """Analyze a mail and create task records from actionable items."""
    existing_tasks = db.query(Task).filter(Task.source_mail_id == mail.id).all()
    if existing_tasks:
        mail.is_processed = True
        db.commit()
        return [_task_to_ai_schema(task) for task in existing_tasks]

    if mail.is_processed:
        return []

    prompt = MAIL_ANALYSIS_PROMPT.format(
        subject=mail.subject,
        sender=f"{mail.sender_name} <{mail.sender_email}>",
        body=mail.body_preview,
    )

    result_text = chat_complete([], prompt)
    tasks_data = _parse_json_response(result_text)

    created = []
    for t in tasks_data:
        task = create_task(
            db,
            TaskCreate(
                title=t.get("title", "Untitled"),
                description=t.get("description", ""),
                priority=t.get("priority", "medium"),
                source_type="mail",
                source_mail_id=mail.id,
            ),
        )
        created.append(_task_to_ai_schema(task))

    mail.is_processed = True
    db.commit()

    return created


def _task_to_ai_schema(task: Task) -> AiTaskSchema:
    return AiTaskSchema(
        title=task.title,
        description=task.description,
        priority=task.priority,
    )


def _tasks_by_mail(db: Session, mail_ids: list[str]) -> dict[str, list[AiTaskSchema]]:
    """Group a mail's AI-generated tasks by source_mail_id (batched query)."""
    result: dict[str, list[AiTaskSchema]] = {mid: [] for mid in mail_ids}
    if not mail_ids:
        return result
    tasks = db.query(Task).filter(Task.source_mail_id.in_(mail_ids)).all()
    for t in tasks:
        if t.source_mail_id in result:
            result[t.source_mail_id].append(_task_to_ai_schema(t))
    return result


def _parse_json_response(text: str) -> list[dict]:
    """Parse LLM response text into a JSON list, handling markdown code blocks."""
    text = text.strip()
    # 尝试提取 markdown 代码块中的 JSON
    md_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if md_match:
        text = md_match.group(1).strip()
    # 尝试提取 JSON 数组
    arr_match = re.search(r"\[.*\]", text, re.DOTALL)
    if arr_match:
        text = arr_match.group(0)
    return json.loads(text)
