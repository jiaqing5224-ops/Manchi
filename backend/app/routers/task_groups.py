"""Task groups router — CRUD for done-column directories."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.models.task_group import TaskGroup
from app.schemas.task_group import TaskGroupCreate, TaskGroupUpdate, TaskGroupResponse

router = APIRouter(prefix="/api/task-groups", tags=["task-groups"])


@router.get("")
def list_groups(db: Session = Depends(get_db)) -> list[TaskGroupResponse]:
    groups = db.query(TaskGroup).order_by(TaskGroup.created_at.asc()).all()
    return [TaskGroupResponse.model_validate(g) for g in groups]


@router.post("", status_code=201)
def create_group(data: TaskGroupCreate, db: Session = Depends(get_db)) -> TaskGroupResponse:
    group = TaskGroup(name=data.name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return TaskGroupResponse.model_validate(group)


@router.put("/{group_id}")
def update_group(group_id: int, data: TaskGroupUpdate, db: Session = Depends(get_db)) -> TaskGroupResponse:
    group = db.query(TaskGroup).filter(TaskGroup.id == group_id).first()
    if not group:
        raise HTTPException(404, "Group not found")
    if data.name is not None:
        group.name = data.name
    db.commit()
    db.refresh(group)
    return TaskGroupResponse.model_validate(group)


@router.delete("/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    group = db.query(TaskGroup).filter(TaskGroup.id == group_id).first()
    if not group:
        raise HTTPException(404, "Group not found")
    # Ungroup tasks in this directory rather than deleting them.
    db.query(Task).filter(Task.group_id == group_id).update({Task.group_id: None})
    db.delete(group)
    db.commit()
    return {"ok": True}
