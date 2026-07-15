"""
Task router — CRUD for tasks.
"""

import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.mail import Mail
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse
from app.services import task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("")
def list_tasks(status: str | None = None, db: Session = Depends(get_db)):
    tasks = task_service.list_tasks(db, status=status)
    return [TaskResponse.model_validate(t) for t in tasks]


@router.get("/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = task_service.get_task(db, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return TaskResponse.model_validate(task)


@router.get("/{task_id}/context")
def get_task_context(task_id: int, db: Session = Depends(get_db)):
    """Return the task's source context — original mail / text / file content.

    Used by both "查看原文" and "AI 协助" so the frontend can render the source
    or feed it to the chatbot without duplicating extraction logic.
    """
    task = task_service.get_task(db, task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    source_type = _infer_source_type(task)

    result: dict = {
        "task_id": task.id,
        "title": task.title,
        "description": task.description or "",
        "source_type": source_type,
        "source_meta": {},
        "source_content": "",
    }

    if source_type == "mail" and task.source_mail_id:
        mail = db.query(Mail).filter(Mail.id == task.source_mail_id).first()
        if mail:
            result["source_meta"] = {
                "mail_id": mail.id,
                "subject": mail.subject,
                "sender_name": mail.sender_name,
                "sender_email": mail.sender_email,
                "received_at": mail.received_at.isoformat() if mail.received_at else None,
            }
            result["source_content"] = mail.body_preview or ""
        else:
            result["source_meta"] = {"mail_id": task.source_mail_id, "not_found": True}
    elif source_type == "text":
        result["source_meta"] = {"char_count": len(task.source_text or "")}
        result["source_content"] = task.source_text or ""
    elif source_type == "file" and task.source_file_path:
        file_path = task.source_file_path
        p = Path(file_path)
        meta: dict = {"file_path": file_path, "file_name": p.name if p.name else file_path}
        if not p.is_file():
            meta["not_found"] = True
            result["source_content"] = ""
        else:
            meta["file_size"] = p.stat().st_size
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    result["source_content"] = f.read()
            except OSError as e:
                meta["read_error"] = str(e)
                result["source_content"] = ""
        result["source_meta"] = meta

    return result


def _infer_source_type(task) -> str | None:
    """Infer source type, falling back to legacy source_mail_id."""
    if task.source_type in ("mail", "text", "file"):
        return task.source_type
    if task.source_mail_id:
        return "mail"
    if task.source_text:
        return "text"
    if task.source_file_path:
        return "file"
    return None


@router.post("", status_code=201)
def create_task(data: TaskCreate, db: Session = Depends(get_db)):
    task = task_service.create_task(db, data)
    return TaskResponse.model_validate(task)


@router.put("/{task_id}")
def update_task(task_id: int, data: TaskUpdate, db: Session = Depends(get_db)):
    task = task_service.update_task(db, task_id, data)
    if not task:
        raise HTTPException(404, "Task not found")
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    ok = task_service.delete_task(db, task_id)
    if not ok:
        raise HTTPException(404, "Task not found")
    return {"ok": True}
