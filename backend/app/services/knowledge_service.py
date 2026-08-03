"""Knowledge precipitation service.

Gathers a task's full chain (the task itself + its source content) and asks the
LLM to draft a reusable "knowledge card" summary. The summary is editable by
the user before being saved via the knowledge router.
"""

import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models.mail import Mail
from app.models.task import Task
from app.services.llm.client import chat_complete
from app.services.llm.prompts import KNOWLEDGE_PROMPT


def _infer_source_type(task: Task) -> Optional[str]:
    if task.source_type in ("mail", "text", "file"):
        return task.source_type
    if task.source_mail_id:
        return "mail"
    if task.source_text:
        return "text"
    if task.source_file_path:
        return "file"
    return None


def gather_chain(db: Session, task: Task) -> dict:
    """Collect the full chain of a task into a plain dict for the LLM.

    Includes the task's own fields plus its originating source content
    (mail subject/sender/body, raw text, or file path). Artifact linkage is a
    forward-looking item — tasks don't yet reference a rule_id, so produced
    files are not attached here yet.
    """
    source_type = _infer_source_type(task)
    chain: dict = {
        "task": {
            "id": task.id,
            "title": task.title,
            "description": task.description or "",
            "priority": task.priority,
            "status": task.status,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "created_at": task.created_at.isoformat() if task.created_at else None,
        },
        "source_type": source_type,
        "source": {},
    }

    if source_type == "mail" and task.source_mail_id:
        mail = db.query(Mail).filter(Mail.id == task.source_mail_id).first()
        if mail:
            chain["source"] = {
                "kind": "mail",
                "subject": mail.subject,
                "sender_name": mail.sender_name,
                "sender_email": mail.sender_email,
                "received_at": mail.received_at.isoformat() if mail.received_at else None,
                "body_preview": mail.body_preview or "",
            }
        else:
            chain["source"] = {"kind": "mail", "not_found": True}
    elif source_type == "text":
        chain["source"] = {"kind": "text", "content": task.source_text or ""}
    elif source_type == "file" and task.source_file_path:
        chain["source"] = {"kind": "file", "path": task.source_file_path}
    else:
        chain["source"] = {"kind": "unknown"}

    return chain


def draft_summary(chain: dict) -> str:
    """Ask the LLM to turn a chain dict into a structured knowledge summary.

    Falls back to a template built directly from the chain data when the LLM
    is not configured or errors, so the feature still produces an editable
    draft instead of failing.
    """
    chain_text = json.dumps(chain, ensure_ascii=False, indent=2)
    prompt = KNOWLEDGE_PROMPT.format(chain=chain_text)
    try:
        return chat_complete([], prompt)
    except Exception:
        return _template_summary(chain)


def _template_summary(chain: dict) -> str:
    """Build a structured knowledge card from the chain data without an LLM."""
    task = chain.get("task", {})
    source = chain.get("source", {})
    src_kind = source.get("kind")

    if src_kind == "mail":
        background = (
            f"本任务来源于邮件《{source.get('subject', '')}》，"
            f"发件人 {source.get('sender_name', '')} <{source.get('sender_email', '')}>。"
        )
        raw = source.get("body_preview", "")
    elif src_kind == "text":
        background = "本任务来源于一段文本输入。"
        raw = source.get("content", "")
    elif src_kind == "file":
        background = f"本任务来源于文件：{source.get('path', '')}。"
        raw = ""
    else:
        background = "来源未知。"
        raw = ""

    key_points = raw.strip().replace("\n", " ")[:300] if raw.strip() else "（暂无来源正文可供提炼）"

    return (
        "## 背景\n"
        f"{background}\n\n"
        "## 核心要点与决策\n"
        f"- {key_points}\n\n"
        "## 行动项与结果\n"
        f"- 任务：{task.get('title', '')}\n"
        f"- 优先级：{task.get('priority', '')}｜状态：{task.get('status', '')}\n\n"
        "## 关联资源\n"
        f"- 来源类型：{chain.get('source_type') or src_kind}\n\n"
        "## 经验沉淀\n"
        "- （待补充：本次处理中的注意事项、可复用经验、待跟进事项）\n"
    )
