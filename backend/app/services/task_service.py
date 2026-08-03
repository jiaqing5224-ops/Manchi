"""Task CRUD service layer."""

from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate


def list_tasks(
    db: Session,
    status: str | None = None,
    priority: str | None = None,
    keyword: str | None = None,
    date_field: str = "created_at",
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[Task]:
    query = db.query(Task)
    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            Task.title.ilike(like) | Task.description.ilike(like)
        )
    if date_field in ("created_at", "due_date"):
        col = getattr(Task, date_field)
        if date_from:
            query = query.filter(func.date(col) >= date_from)
        if date_to:
            query = query.filter(func.date(col) <= date_to)
    return query.order_by(Task.created_at.desc()).all()


def get_task(db: Session, task_id: int) -> Task | None:
    return db.query(Task).filter(Task.id == task_id).first()


def create_task(db: Session, data: TaskCreate) -> Task:
    task = Task(**data.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, task_id: int, data: TaskUpdate) -> Task | None:
    task = get_task(db, task_id)
    if not task:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task_id: int) -> bool:
    task = get_task(db, task_id)
    if not task:
        return False
    db.delete(task)
    db.commit()
    return True
