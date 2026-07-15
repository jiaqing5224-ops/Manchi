"""
Mail router — scan Outlook, list cached mails, AI analysis.
"""

import json
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.mail import Mail
from app.models.task import Task
from app.schemas.mail import MailResponse, AnalyzeResult, AiTaskSchema
from app.services.outlook.mail_handler import scan_inbox
from app.services.llm.client import chat_complete
from app.services.llm.prompts import MAIL_ANALYSIS_PROMPT
from app.services.task_service import create_task
from app.schemas.task import TaskCreate

router = APIRouter(prefix="/api/mail", tags=["mail"])


@router.post("/scan")
def scan_mails(db: Session = Depends(get_db)):
    """Scan Outlook inbox, cache new mails, and generate tasks for them."""
    try:
        mails = scan_inbox(max_items=50)
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    count = 0
    tasks_count = 0
    failed_count = 0
    for m in mails:
        existing = db.query(Mail).filter(Mail.id == m.entry_id).first()
        if existing:
            if not existing.is_processed:
                try:
                    tasks_count += _create_missing_tasks_for_scan(db, existing)
                except Exception:
                    db.rollback()
                    failed_count += 1
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
        except Exception:
            db.rollback()
            failed_count += 1
    return {"scanned": count, "total": len(mails), "tasks_created": tasks_count, "analysis_failed": failed_count}


@router.get("")
def list_mails(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """List cached mails, most recent first."""
    mails = (
        db.query(Mail)
        .order_by(Mail.received_at.desc().nullslast())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [MailResponse.model_validate(m) for m in mails]


@router.get("/{mail_id}")
def get_mail(mail_id: str, db: Session = Depends(get_db)):
    """Get a single mail by ID."""
    mail = db.query(Mail).filter(Mail.id == mail_id).first()
    if not mail:
        raise HTTPException(404, "Mail not found")
    return MailResponse.model_validate(mail)


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
