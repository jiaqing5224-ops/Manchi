"""Tool schemas and executor for LLM function calling.

Each tool wraps an existing platform capability (mail scanning, task CRUD,
mail analysis, meeting report) so the LLM can invoke them via function call.
"""

import json
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models.mail import Mail
from app.schemas.task import TaskCreate
from app.services.llm.client import chat_complete
from app.services.llm.prompts import MAIL_ANALYSIS_PROMPT
from app.services.outlook.mail_handler import scan_inbox
from app.services.task_service import create_task, list_tasks


TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "scan_mails",
            "description": "扫描 Outlook 收件箱的新邮件并存入数据库缓存",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_items": {
                        "type": "integer",
                        "description": "最多扫描的邮件数量，默认 50",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_mails",
            "description": "列出数据库中已缓存的邮件，按时间倒序",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "返回邮件数量，默认 10",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "列出当前任务列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["todo", "in_progress", "done"],
                        "description": "按状态过滤，不传则返回全部",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "创建一个新任务。每次调用只能创建一个任务，如需创建多个请多次调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "任务标题"},
                    "description": {"type": "string", "description": "任务描述"},
                    "priority": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "优先级，默认 medium",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_mail",
            "description": "AI 分析指定邮件并自动生成待办任务",
            "parameters": {
                "type": "object",
                "properties": {
                    "mail_id": {"type": "string", "description": "邮件 ID"}
                },
                "required": ["mail_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_meeting_report",
            "description": "扫描本周会议邮件并生成 Excel 报告保存到桌面",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_mail",
            "description": "在 Outlook 中创建邮件草稿（不自动发送）。用户需在 Outlook 草稿箱检查后手动发送。多个收件人/抄送用分号分隔。",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "收件人邮箱，多个用分号分隔"},
                    "subject": {"type": "string", "description": "邮件主题"},
                    "body": {"type": "string", "description": "邮件正文（纯文本）"},
                    "cc": {"type": "string", "description": "抄送邮箱，多个用分号分隔（可选）"}
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_rule",
            "description": "创建一个自动化编排规则。规则定义了输入源、触发方式和动作链，用于自动处理邮件、文本或文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "规则名称"},
                    "description": {"type": "string", "description": "规则描述"},
                    "source_type": {
                        "type": "string",
                        "enum": ["mail", "text", "file"],
                        "description": "输入源类型：mail=邮件, text=自定义文本, file=选择文件",
                    },
                    "days_range": {
                        "type": "integer",
                        "description": "当输入源为邮件时，扫描最近N天（默认7）",
                    },
                    "content": {
                        "type": "string",
                        "description": "当输入源为文本时，要处理的文本内容",
                    },
                    "trigger_type": {
                        "type": "string",
                        "enum": ["manual", "schedule", "new_mail"],
                        "description": "触发方式：manual=手动, schedule=定时, new_mail=新邮件到达",
                    },
                    "cron": {
                        "type": "string",
                        "description": "当触发方式为定时时，cron 表达式，如 '0 9 * * *' 表示每天9点",
                    },
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": [
                                        "ai_extract", "ai_summarize", "ai_classify",
                                        "export_excel", "export_json", "export_markdown",
                                        "create_task", "excel_workload_export", "notify"
                                    ],
                                    "description": "动作类型"
                                },
                                "params": {
                                    "type": "object",
                                    "description": "动作参数，依赖具体类型。如 ai_extract 需要 fields(数组)和 prompt_extra(字符串)；export_excel 需要 columns(数组)和 filename(字符串)"
                                }
                            },
                            "required": ["type"]
                        },
                        "description": "动作链，按顺序执行的动作列表"
                    }
                },
                "required": ["name", "source_type", "trigger_type", "actions"],
            },
        },
    },
]


def execute_tool(name: str, args: dict, db: Session) -> str:
    """Dispatch a tool call by name. Returns a JSON string result."""
    try:
        if name == "scan_mails":
            return _scan_mails(db, _as_int(args.get("max_items"), 50))
        if name == "list_mails":
            return _list_mails(db, _as_int(args.get("limit"), 10))
        if name == "list_tasks":
            status = _as_str(args.get("status"))
            return _list_tasks(db, status)
        if name == "create_task":
            return _create_task(db, args)
        if name == "analyze_mail":
            mail_id = _as_str(args.get("mail_id"))
            if not mail_id:
                return json.dumps({"error": "mail_id is required"})
            return _analyze_mail(db, mail_id)
        if name == "generate_meeting_report":
            return _generate_meeting_report(db)
        if name == "send_mail":
            return _send_mail(db, args)
        if name == "create_rule":
            return _create_rule(db, args)
        return json.dumps({"error": f"unknown tool: {name}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _scan_mails(db: Session, max_items: int) -> str:
    mails = scan_inbox(max_items=max_items)
    count = 0
    for m in mails:
        if db.query(Mail).filter(Mail.id == m.entry_id).first():
            continue
        db.add(
            Mail(
                id=m.entry_id,
                subject=m.subject,
                sender_name=m.sender_name,
                sender_email=m.sender_email,
                body_preview=m.body_preview,
                received_at=m.received_at,
            )
        )
        count += 1
    db.commit()
    return json.dumps({"scanned": count, "total": len(mails)}, ensure_ascii=False)


def _list_mails(db: Session, limit: int) -> str:
    mails = (
        db.query(Mail)
        .order_by(Mail.received_at.desc().nullslast())
        .limit(limit)
        .all()
    )
    return json.dumps(
        [
            {
                "id": m.id,
                "subject": m.subject,
                "sender": f"{m.sender_name} <{m.sender_email}>",
                "received_at": m.received_at.isoformat() if m.received_at else None,
                "is_read": m.is_read,
            }
            for m in mails
        ],
        ensure_ascii=False,
    )


def _list_tasks(db: Session, status: Optional[str]) -> str:
    tasks = list_tasks(db, status=status)
    return json.dumps(
        [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "priority": t.priority,
            }
            for t in tasks
        ],
        ensure_ascii=False,
    )


def _create_task(db: Session, args: dict) -> str:
    title = _as_str(args.get("title"))
    if not title:
        return json.dumps({"error": "title is required"})
    task = create_task(
        db,
        TaskCreate(
            title=title,
            description=_as_str(args.get("description")) or "",
            priority=_as_str(args.get("priority")) or "medium",
        ),
    )
    return json.dumps(
        {"id": task.id, "title": task.title, "priority": task.priority},
        ensure_ascii=False,
    )


def _analyze_mail(db: Session, mail_id: str) -> str:
    mail = db.query(Mail).filter(Mail.id == mail_id).first()
    if not mail:
        return json.dumps({"error": "mail not found"})
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
                source_mail_id=mail_id,
            ),
        )
        created.append({"title": task.title, "priority": task.priority})
    mail.is_processed = True
    db.commit()
    return json.dumps({"mail_id": mail_id, "tasks": created}, ensure_ascii=False)


def _generate_meeting_report(db: Session) -> str:
    # Lazy import — meeting_service is built in a later step.
    from app.services.meeting.meeting_service import generate_meeting_excel

    result = generate_meeting_excel(db)
    return json.dumps(result, ensure_ascii=False)


def _send_mail(db: Session, args: dict) -> str:
    """Create an Outlook mail draft (not auto-sent) via win32com COM."""
    import concurrent.futures

    to = _as_str(args.get("to")) or ""
    subject = _as_str(args.get("subject")) or ""
    body = _as_str(args.get("body")) or ""
    cc = _as_str(args.get("cc")) or ""

    if not to or not subject or not body:
        return json.dumps({"error": "to, subject, body 均为必填"}, ensure_ascii=False)

    def _create_draft_in_thread() -> dict:
        """Run COM in a dedicated thread to avoid asyncio event-loop conflicts."""
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)  # 0 = olMailItem
            mail.To = to
            mail.Subject = subject
            mail.Body = body
            if cc:
                mail.CC = cc
            mail.Save()  # Save as draft, do not send
            return {"draft_created": True, "subject": subject, "to": to}
        except Exception as e:
            return {"error": f"创建草稿失败: {e}"}
        finally:
            pythoncom.CoUninitialize()

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(_create_draft_in_thread).result(timeout=30)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"创建草稿失败: {e}"}, ensure_ascii=False)


def _parse_json_response(text: str) -> list[dict]:
    """Parse LLM JSON response, tolerating markdown code fences."""
    text = text.strip()
    md_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if md_match:
        text = md_match.group(1).strip()
    arr_match = re.search(r"\[.*\]", text, re.DOTALL)
    if arr_match:
        text = arr_match.group(0)
    return json.loads(text)


def _create_rule(db: Session, args: dict) -> str:
    name = _as_str(args.get("name"))
    if not name:
        return json.dumps({"error": "name is required"})
    from app.models.rule import Rule

    source_config = {
        "type": _as_str(args.get("source_type")) or "mail",
    }
    if source_config["type"] == "mail":
        source_config["days_range"] = _as_int(args.get("days_range"), 7)
        source_config["sender_filter"] = ""
    elif source_config["type"] == "text":
        source_config["content"] = _as_str(args.get("content")) or ""
    elif source_config["type"] == "file":
        source_config["file_path"] = ""
        source_config["encoding"] = "utf-8"

    trigger_config = {
        "type": _as_str(args.get("trigger_type")) or "manual",
    }
    if trigger_config["type"] == "schedule":
        trigger_config["cron"] = _as_str(args.get("cron")) or "0 9 * * *"

    raw_actions = args.get("actions", [])
    if isinstance(raw_actions, list):
        actions_config = [
            {"type": a.get("type", "notify"), "params": a.get("params", {})}
            for a in raw_actions
            if isinstance(a, dict)
        ]
    else:
        actions_config = []

    rule = Rule(
        name=name,
        description=_as_str(args.get("description")) or "",
        source_config=source_config,
        trigger_config=trigger_config,
        actions_config=actions_config,
        is_active=True,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return json.dumps(
        {"id": rule.id, "name": rule.name, "actions_count": len(actions_config)},
        ensure_ascii=False,
    )


def _as_int(val: object, default: int) -> int:
    return val if isinstance(val, int) else default


def _as_str(val: object) -> Optional[str]:
    return val if isinstance(val, str) else None
