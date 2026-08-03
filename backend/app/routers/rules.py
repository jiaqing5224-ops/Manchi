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
