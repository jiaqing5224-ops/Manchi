"""Knowledge router — precipitate & retrieve task knowledge cards."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.knowledge import TaskKnowledge
from app.models.task import Task
from app.schemas.knowledge import (
    KnowledgeCreate,
    KnowledgeUpdate,
    KnowledgeResponse,
)
from app.services import knowledge_service

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _to_response(k: TaskKnowledge, task: Task | None) -> KnowledgeResponse:
    return KnowledgeResponse(
        id=k.id,
        task_id=k.task_id,
        summary=k.summary,
        created_at=k.created_at,
        updated_at=k.updated_at,
        task_title=task.title if task else "",
        priority=task.priority if task else None,
        status=task.status if task else None,
        source_type=task.source_type if task else None,
        source_mail_id=task.source_mail_id if task else None,
    )


@router.get("")
def list_knowledge(
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
):
    """List all knowledge cards (newest first), optionally bounded by created_at date."""
    query = db.query(TaskKnowledge)
    if date_from:
        query = query.filter(func.date(TaskKnowledge.created_at) >= date_from)
    if date_to:
        query = query.filter(func.date(TaskKnowledge.created_at) <= date_to)
    rows = query.order_by(TaskKnowledge.created_at.desc()).all()

    tasks = {t.id: t for t in db.query(Task).all()}
    return [_to_response(k, tasks.get(k.task_id)) for k in rows]


@router.post("/draft/{task_id}")
def draft_knowledge(task_id: int, db: Session = Depends(get_db)):
    """Generate a draft knowledge summary for a task (does NOT persist).

    Returns the AI-generated markdown plus the chain snapshot, so the frontend
    can show an editable dialog and then POST it to /api/knowledge to save.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")

    try:
        chain = knowledge_service.gather_chain(db, task)
        summary = knowledge_service.draft_summary(chain)
    except Exception as e:
        raise HTTPException(500, f"生成知识草稿失败: {e}")
    return {
        "task_id": task_id,
        "summary": summary,
        "chain_context": json.dumps(chain, ensure_ascii=False),
    }


@router.post("", status_code=201)
def create_knowledge(data: KnowledgeCreate, db: Session = Depends(get_db)):
    """Save (upsert by task_id) a knowledge card."""
    task = db.query(Task).filter(Task.id == data.task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")

    existing = (
        db.query(TaskKnowledge).filter(TaskKnowledge.task_id == data.task_id).first()
    )
    if existing:
        existing.summary = data.summary
        if data.chain_context is not None:
            existing.chain_context = data.chain_context
        db.commit()
        db.refresh(existing)
        return _to_response(existing, task)

    k = TaskKnowledge(
        task_id=data.task_id,
        summary=data.summary,
        chain_context=data.chain_context or "",
    )
    db.add(k)
    db.commit()
    db.refresh(k)
    return _to_response(k, task)


@router.get("/{knowledge_id}")
def get_knowledge(knowledge_id: int, db: Session = Depends(get_db)):
    k = db.query(TaskKnowledge).filter(TaskKnowledge.id == knowledge_id).first()
    if not k:
        raise HTTPException(404, "Knowledge not found")
    task = db.query(Task).filter(Task.id == k.task_id).first()
    return _to_response(k, task)


@router.put("/{knowledge_id}")
def update_knowledge(
    knowledge_id: int, data: KnowledgeUpdate, db: Session = Depends(get_db)
):
    k = db.query(TaskKnowledge).filter(TaskKnowledge.id == knowledge_id).first()
    if not k:
        raise HTTPException(404, "Knowledge not found")
    k.summary = data.summary
    db.commit()
    db.refresh(k)
    task = db.query(Task).filter(Task.id == k.task_id).first()
    return _to_response(k, task)


@router.delete("/{knowledge_id}")
def delete_knowledge(knowledge_id: int, db: Session = Depends(get_db)):
    k = db.query(TaskKnowledge).filter(TaskKnowledge.id == knowledge_id).first()
    if not k:
        raise HTTPException(404, "Knowledge not found")
    db.delete(k)
    db.commit()
    return {"ok": True}
