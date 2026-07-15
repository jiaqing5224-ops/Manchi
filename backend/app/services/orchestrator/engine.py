"""Pipeline executor — orchestrates source → actions[] for a rule.

The executor is the single entry point for running an orchestration rule:
it reads the rule's three config blocks, fetches input from the source,
then walks the action chain, threading the data through each step.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.rule import Rule
from app.services.meeting.meeting_service import get_exports_dir

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """Mutable context threaded through every step of a pipeline run."""

    rule_id: int
    rule_name: str
    artifacts_dir: str
    db: Any = None  # sqlalchemy.orm.Session, used by actions that persist data
    input_data: Any = None
    current_data: Any = None
    artifacts: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    # Source provenance — recorded by the executor so downstream actions
    # (e.g. create_task) can stamp tasks with their origin for "查看原文".
    source_type: str = ""          # mail / text / file
    source_content: str = ""       # original text (text source) or file content
    source_file_path: str = ""     # file path (file source only)


def _slugify(name: str) -> str:
    """Turn a rule name into a filesystem-safe directory fragment."""
    cleaned = re.sub(r"[^\w\u4e00-\u9fa5\-]+", "_", name.strip())
    return cleaned[:40] or "rule"


def get_rule_artifacts_dir(rule_id: int, rule_name: str) -> str:
    """Return (creating if needed) the per-rule artifacts subdirectory."""
    path = Path(get_exports_dir()) / f"{rule_id}_{_slugify(rule_name)}"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


class PipelineExecutor:
    """Runs a Rule's pipeline: source → actions[]."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def run(self, rule_id: int) -> dict[str, Any]:
        """Execute the rule's pipeline and return a summary dict.

        Sets rule.last_run_at / last_run_status / last_run_message so the UI
        can show the most recent outcome.
        """
        from app.services.orchestrator.sources import fetch_source
        from app.services.orchestrator.actions import run_action

        rule = self.db.query(Rule).filter(Rule.id == rule_id).first()
        if rule is None:
            raise ValueError(f"Rule {rule_id} not found")

        started_at = datetime.now()
        ctx = PipelineContext(
            rule_id=rule.id,
            rule_name=rule.name,
            artifacts_dir=get_rule_artifacts_dir(rule.id, rule.name),
            db=self.db,
        )

        status = "success"
        message = ""

        try:
            # 1. Fetch source data
            source_config = rule.source_config or {"type": "text", "content": ""}
            ctx.source_type = str(source_config.get("type", "text"))
            ctx.input_data = fetch_source(source_config, ctx)
            ctx.current_data = ctx.input_data
            # Record source provenance so create_task can stamp tasks.
            # Mail source keeps using source_mail_id (set per-item in the action);
            # text / file sources carry their content / path for "查看原文".
            if ctx.source_type == "text":
                ctx.source_content = str(source_config.get("content", ""))
            elif ctx.source_type == "file":
                ctx.source_file_path = str(source_config.get("file_path", ""))
                if isinstance(ctx.input_data, str):
                    ctx.source_content = ctx.input_data

            # 2. Run action chain
            actions_config = rule.actions_config or []
            if not actions_config:
                ctx.steps.append("无动作配置，直接结束")
            for i, action_cfg in enumerate(actions_config):
                action_type = action_cfg.get("type", "unknown")
                ctx.steps.append(f"[{i + 1}/{len(actions_config)}] 执行 {action_type}")
                ctx.current_data = run_action(action_cfg, ctx)

        except Exception as e:
            logger.exception("Pipeline run failed for rule %s", rule_id)
            status = "failed"
            message = str(e)
            ctx.steps.append(f"执行失败：{message}")

        finished_at = datetime.now()

        # Persist run metadata
        rule.last_run_at = finished_at
        rule.last_run_status = status
        rule.last_run_message = message or ("；".join(ctx.steps[-3:]) if ctx.steps else "")
        self.db.commit()

        return {
            "rule_id": rule.id,
            "status": status,
            "message": message,
            "artifacts": ctx.artifacts,
            "steps": ctx.steps,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
        }
