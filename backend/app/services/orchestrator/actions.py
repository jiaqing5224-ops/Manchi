"""Pipeline actions — composable, chainable transformation steps.

Each action takes (params, ctx) and returns a new value for ctx.current_data.
Actions that produce artifacts (export_excel, export_json) append file paths
to ctx.artifacts but pass current_data through unchanged so the chain can
continue with the same payload.

AI actions accept either str or a list (of mails / dicts); the data is
serialized to text before being sent to the LLM.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from app.services.orchestrator.engine import PipelineContext

logger = logging.getLogger(__name__)


# ---- Serialization helpers ----

def _to_text(data: Any) -> str:
    """Serialize any pipeline data shape to text for LLM consumption."""
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    if isinstance(data, (list, tuple)):
        parts: list[str] = []
        for i, item in enumerate(data):
            parts.append(_item_to_text(item, i))
        return "\n---\n".join(parts)
    if isinstance(data, dict):
        return json.dumps(data, ensure_ascii=False, indent=2)
    return str(data)


def _item_to_text(item: Any, index: int) -> str:
    """Format a single list item (mail / dict / str) as readable text."""
    if isinstance(item, str):
        return f"[{index}] {item}"
    if isinstance(item, dict):
        return f"[{index}] " + json.dumps(item, ensure_ascii=False)
    # OutlookMail-like object
    subject = getattr(item, "subject", "")
    sender = getattr(item, "sender_email", "") or getattr(item, "sender_name", "")
    body = getattr(item, "full_body", "") or ""
    return f"[{index}] 主题: {subject} | 发件人: {sender}\n正文: {body[:1500]}"


def _parse_llm_json(text: str) -> Any:
    """Parse JSON from LLM output, tolerating markdown fences and extra prose."""
    text = text.strip()
    md = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if md:
        text = md.group(1).strip()
    arr = re.search(r"\[.*\]", text, re.DOTALL)
    obj = re.search(r"\{.*\}", text, re.DOTALL)
    if arr:
        text = arr.group(0)
    elif obj:
        text = obj.group(0)
    return json.loads(text)


# ---- AI actions ----

def _action_ai_extract(params: dict[str, Any], ctx: PipelineContext) -> list[dict[str, Any]]:
    """Ask the LLM to extract structured fields from the input text."""
    from app.services.llm.client import chat_complete

    fields = params.get("fields", [])
    if isinstance(fields, str):
        fields = [f.strip() for f in fields.split(",") if f.strip()]
    prompt_extra = str(params.get("prompt_extra", "")).strip()

    text_input = _to_text(ctx.current_data)
    if not text_input:
        ctx.steps.append("AI提取：输入为空，跳过")
        return []

    fields_desc = "、".join(fields) if fields else "相关信息"
    prompt = (
        f"你是信息提取助手。从下面的文本中提取以下字段：{fields_desc}。\n"
        f"返回 JSON 数组，每个元素是一个对象，包含这些字段（无法判断的字段填 null）。\n"
        f"只返回 JSON 数组，不要多余文字。\n\n"
        f"{prompt_extra}\n\n文本：\n{text_input}"
    )
    try:
        raw = chat_complete([], prompt, temperature=0.0)
        result = _parse_llm_json(raw)
        if not isinstance(result, list):
            result = [result] if isinstance(result, dict) else []
        ctx.steps.append(f"AI提取：提取到 {len(result)} 条结构化记录")
        return result
    except Exception as e:
        logger.error("ai_extract failed: %s", e)
        ctx.steps.append(f"AI提取：失败 ({e})")
        return []


def _action_ai_summarize(params: dict[str, Any], ctx: PipelineContext) -> str:
    """Generate a Chinese summary of the input text."""
    from app.services.llm.client import chat_complete

    max_length = int(params.get("max_length", 300))
    text_input = _to_text(ctx.current_data)
    if not text_input:
        ctx.steps.append("AI摘要：输入为空，跳过")
        return ""

    prompt = (
        f"请用中文对下面的内容生成一份不超过 {max_length} 字的摘要，"
        f"突出关键信息，条理清晰：\n\n{text_input}"
    )
    try:
        result = chat_complete([], prompt, temperature=0.3)
        ctx.steps.append(f"AI摘要：生成 {len(result)} 字摘要")
        return result
    except Exception as e:
        logger.error("ai_summarize failed: %s", e)
        ctx.steps.append(f"AI摘要：失败 ({e})")
        return ""


def _action_ai_classify(params: dict[str, Any], ctx: PipelineContext) -> list[dict[str, Any]]:
    """Classify each item in the input into one of the provided categories."""
    from app.services.llm.client import chat_complete

    categories = params.get("categories", ["常规"])
    if isinstance(categories, str):
        categories = [c.strip() for c in categories.split(",") if c.strip()]
    cats_desc = "、".join(categories)

    text_input = _to_text(ctx.current_data)
    if not text_input:
        ctx.steps.append("AI分类：输入为空，跳过")
        return []

    prompt = (
        f"你是分类助手。将下面的每条内容归入以下类别之一：{cats_desc}。\n"
        f"返回 JSON 数组，每个元素格式：{{\"index\": int, \"tag\": \"类别\", \"reason\": \"简短理由\"}}。\n"
        f"只返回 JSON 数组。\n\n内容：\n{text_input}"
    )
    try:
        raw = chat_complete([], prompt, temperature=0.0)
        result = _parse_llm_json(raw)
        if not isinstance(result, list):
            result = [result] if isinstance(result, dict) else []
        ctx.steps.append(f"AI分类：分类 {len(result)} 条")
        return result
    except Exception as e:
        logger.error("ai_classify failed: %s", e)
        ctx.steps.append(f"AI分类：失败 ({e})")
        return []


def _action_ai_meeting_extract(params: dict[str, Any], ctx: PipelineContext) -> list[dict[str, Any]]:
    """Extract meetings from emails using the proven batch-meeting logic.

    Reuses meeting_service._batch_extract_meetings so behavior is identical
    to the Dashboard "生成本周会议Excel" feature — same prompt, same batching,
    same is_meeting filtering.
    """
    from app.services.meeting.meeting_service import _batch_extract_meetings

    data = ctx.current_data
    if not isinstance(data, list) or not data:
        ctx.steps.append("AI会议提取：输入为空，跳过")
        return []

    try:
        meetings = _batch_extract_meetings(data)
        # 构建 subject -> entry_id 映射，用于后续 create_task 跳转邮件
        subject_to_entry: dict[str, str] = {}
        for mail_obj in data:
            sid = getattr(mail_obj, "entry_id", None) or getattr(mail_obj, "id", None)
            subj = getattr(mail_obj, "subject", "")
            if sid and subj:
                subject_to_entry[subj.strip()] = str(sid)

        result: list[dict[str, Any]] = []
        for m in meetings:
            result.append({
                "subject": m.subject,
                "start_time": m.start_time.strftime("%Y-%m-%d %H:%M") if m.start_time else "",
                "end_time": m.end_time.strftime("%Y-%m-%d %H:%M") if m.end_time else "",
                "duration_hours": m.duration_hours if m.duration_hours is not None else "",
                "entry_id": subject_to_entry.get(m.subject.strip(), ""),
            })
        ctx.steps.append(f"AI会议提取：识别 {len(result)} 条会议")
        return result
    except Exception as e:
        logger.error("ai_meeting_extract failed: %s", e)
        ctx.steps.append(f"AI会议提取：失败 ({e})")
        return []


# ---- Export actions (produce artifacts, pass data through) ----

def _action_export_excel(params: dict[str, Any], ctx: PipelineContext) -> Any:
    """Write current_data (list[dict]) to a styled Excel file in the artifacts dir.

    Always writes a file — even when data is empty — so the user can see the
    pipeline produced an artifact. When empty, a row with headers (or a
    placeholder) is written.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    data = ctx.current_data
    if not isinstance(data, list):
        data = [data] if data else []

    columns = params.get("columns", [])
    if isinstance(columns, str):
        columns = [c.strip() for c in columns.split(",") if c.strip()]

    if columns:
        headers = list(columns)
    elif data and isinstance(data[0], dict):
        headers = list(data[0].keys())
    else:
        headers = ["内容"]

    rows: list[list[Any]] = []
    for item in data:
        if isinstance(item, dict):
            rows.append([item.get(h, "") for h in headers])
        else:
            rows.append([str(item)])

    wb = Workbook()
    ws = wb.active
    ws.title = "数据"
    ws.append(headers)
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4FC3F7", end_color="4FC3F7", fill_type="solid")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
    if rows:
        for row in rows:
            ws.append(row)
    else:
        ws.append(["（暂无数据）"])

    for i in range(1, len(headers) + 1):
        ws.column_dimensions[chr(64 + i) if i <= 26 else "A"].width = 24

    filename = params.get("filename") or f"导出_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    path = str(Path(ctx.artifacts_dir) / filename)
    wb.save(path)
    ctx.artifacts.append(path)
    ctx.steps.append(f"导出Excel：{filename}（{len(rows)} 行）")
    return data


def _action_export_json(params: dict[str, Any], ctx: PipelineContext) -> Any:
    """Write current_data to a JSON file in the artifacts dir."""
    indent = int(params.get("indent", 2))
    filename = params.get("filename") or f"导出_{datetime.now():%Y%m%d_%H%M%S}.json"
    path = str(Path(ctx.artifacts_dir) / filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ctx.current_data, f, ensure_ascii=False, indent=indent, default=str)
    ctx.artifacts.append(path)
    ctx.steps.append(f"导出JSON：{filename}")
    return ctx.current_data


def _action_notify(params: dict[str, Any], ctx: PipelineContext) -> Any:
    """Record a notification step (no-op stub for now — tray notification later)."""
    message = str(params.get("message", "编排执行完成"))
    ctx.steps.append(f"通知：{message}")
    return ctx.current_data


def _to_markdown(data: Any, title: str = "") -> str:
    """Render pipeline data as a readable markdown document."""
    lines: list[str] = []
    if title:
        lines.append(f"# {title}")
        lines.append("")

    if data is None:
        lines.append("（无数据）")
        return "\n".join(lines)

    if isinstance(data, str):
        lines.append(data)
        return "\n".join(lines)

    if isinstance(data, dict):
        lines.append("| 字段 | 值 |")
        lines.append("| --- | --- |")
        for k, v in data.items():
            cell = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
            lines.append(f"| {k} | {cell} |")
        return "\n".join(lines)

    if isinstance(data, list):
        if not data:
            lines.append("（空列表）")
            return "\n".join(lines)
        if isinstance(data[0], dict):
            keys: list[str] = []
            for item in data:
                for k in item.keys():
                    if k not in keys:
                        keys.append(k)
            lines.append("| " + " | ".join(keys) + " |")
            lines.append("| " + " | ".join("---" for _ in keys) + " |")
            for item in data:
                cells = []
                for k in keys:
                    v = item.get(k, "")
                    cells.append(json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v))
                lines.append("| " + " | ".join(cells) + " |")
        else:
            for i, item in enumerate(data):
                lines.append(f"{i + 1}. {item}")
        return "\n".join(lines)

    lines.append(str(data))
    return "\n".join(lines)


def _action_export_markdown(params: dict[str, Any], ctx: PipelineContext) -> Any:
    """Write current_data to a markdown file in the artifacts dir."""
    title = str(params.get("title", "")).strip()
    filename = params.get("filename") or f"导出_{datetime.now():%Y%m%d_%H%M%S}.md"
    path = str(Path(ctx.artifacts_dir) / filename)
    text = _to_markdown(ctx.current_data, title)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    ctx.artifacts.append(path)
    ctx.steps.append(f"导出Markdown：{filename}（{len(text)} 字符）")
    return ctx.current_data


def _action_create_task(params: dict[str, Any], ctx: PipelineContext) -> Any:
    """Create Task records from current_data so they show up in the task center."""
    from app.models.task import Task

    db = ctx.db
    if db is None:
        ctx.steps.append("生成Task：数据库会话不可用，跳过")
        return ctx.current_data

    data = ctx.current_data
    if not isinstance(data, list):
        data = [data] if data else []

    title_field = str(params.get("title_field", "title")).strip() or "title"
    desc_field = str(params.get("desc_field", "description")).strip() or "description"
    priority = str(params.get("priority", "medium")).strip() or "medium"
    if priority not in ("high", "medium", "low"):
        priority = "medium"

    # 从原始输入数据构建 index -> entry_id 映射（用于回溯邮件来源）
    input_data = ctx.input_data if isinstance(ctx.input_data, list) else []
    index_to_entry: dict[int, str] = {}
    for i, obj in enumerate(input_data):
        eid = getattr(obj, "entry_id", None) or getattr(obj, "id", None)
        if eid:
            index_to_entry[i] = str(eid)

    created = 0
    for item in data:
        title = ""
        description = ""
        source_mail_id: str | None = None
        if isinstance(item, dict):
            title = str(item.get(title_field, "")) or str(item.get("subject", "")) or str(item.get("title", "")) or ""
            description = str(item.get(desc_field, "")) or _to_text(item)
            # 优先用 item 自带的 entry_id，否则通过 index 回溯原始邮件
            source_mail_id = str(item.get("entry_id", "") or "") or None
            if not source_mail_id:
                idx = item.get("index", None)
                if isinstance(idx, int) and idx in index_to_entry:
                    source_mail_id = index_to_entry[idx]
        elif isinstance(item, str):
            title = item[:200] if item else ""
            description = item
        else:
            title = str(getattr(item, "subject", "")) or str(getattr(item, "title", "")) or ""
            description = _to_text(item)
            mail_id = getattr(item, "entry_id", None) or getattr(item, "id", None)
            if mail_id:
                source_mail_id = str(mail_id)

        # 过滤无效数据：title 为 None 或空字符串时不创建 Task
        title = title.strip()
        if not title or title.lower() == "none":
            continue

        # 把 pipeline 源信息写到 Task，让"查看原文"能按来源类型分发
        task_source_type = ctx.source_type or None
        task_source_text = ctx.source_content if ctx.source_type == "text" else None
        task_source_file_path = ctx.source_file_path or None if ctx.source_type == "file" else None

        task = Task(
            title=title[:255],
            description=description,
            priority=priority,
            status="todo",
            source_type=task_source_type,
            source_mail_id=source_mail_id,
            source_text=task_source_text,
            source_file_path=task_source_file_path,
        )
        db.add(task)
        created += 1

    db.commit()
    ctx.steps.append(f"生成Task：创建 {created} 条任务")
    return ctx.current_data


def _action_excel_workload_export(params: dict[str, Any], ctx: PipelineContext) -> list[dict[str, Any]]:
    """Read a workload Excel, filter by name, extract this week's hours, export.

    Designed for the "开发资源管理.xlsx" structure:
      - Header row at row 2 (A=开发姓名, C=项目编号, D=项目名称, J=备注, K+=weekly hours)
      - Weekly columns labeled "W{iso_week:02d}-{year}" e.g. "W28-2026"
      - Summary rows prefixed with "👤" should be skipped
      - Rows with no hours in the target week should be skipped

    The source file may be locked by Excel, so we copy to a temp file first.
    """
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    file_path = str(params.get("file_path", "")).strip()
    sheet_name = str(params.get("sheet_name", "周计划主表")).strip()
    name_filter = str(params.get("name_filter", "Cheng Jia Qing")).strip()
    output_filename = params.get("output_filename") or "工时记录.xlsx"

    if not file_path:
        raise ValueError("excel_workload_export 未配置 file_path")

    # Copy to temp to avoid PermissionError when the file is open in Excel.
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".xlsx")
    try:
        import os
        os.close(tmp_fd)
        shutil.copy2(file_path, tmp_path)

        wb_src = load_workbook(tmp_path, read_only=True, data_only=True)
        if sheet_name not in wb_src.sheetnames:
            raise ValueError(f"工作表 '{sheet_name}' 不存在，可用：{wb_src.sheetnames}")
        ws = wb_src[sheet_name]

        # Build header map from row 2: column_name -> column_index (1-based).
        header_map: dict[str, int] = {}
        for cell in ws[2]:
            val = str(cell.value).strip() if cell.value is not None else ""
            if val:
                header_map[val] = cell.column

        # Auto-detect the current week column.
        iso_year, iso_week, _ = datetime.now().isocalendar()
        week_label = f"W{iso_week:02d}-{iso_year}"
        week_col = header_map.get(week_label)
        if week_col is None:
            raise ValueError(
                f"未在表头中找到本周列 '{week_label}'，"
                f"可用列：{list(header_map.keys())[:20]}..."
            )

        # Fixed column indices (1-based): A=1, C=3, D=4, J=10.
        name_col = 1
        project_no_col = 3
        project_name_col = 4
        remark_col = 10

        # Extract rows matching the name filter, skipping summary/empty rows.
        records: list[dict[str, Any]] = []
        for row in ws.iter_rows(min_row=3, values_only=False):
            name_val = row[name_col - 1].value if len(row) >= name_col else None
            name_str = str(name_val).strip() if name_val is not None else ""
            if not name_str:
                continue
            # Skip summary rows (prefixed with 👤).
            if name_str.startswith("👤"):
                continue
            # Only match the target person.
            if name_str != name_filter:
                continue
            # Skip rows with no hours this week.
            week_val = row[week_col - 1].value if len(row) >= week_col else None
            if week_val is None or str(week_val).strip() == "" or week_val == 0:
                continue

            project_no = str(row[project_no_col - 1].value or "").strip() if len(row) >= project_no_col else ""
            project_name = str(row[project_name_col - 1].value or "").strip() if len(row) >= project_name_col else ""
            remark = str(row[remark_col - 1].value or "").strip() if len(row) >= remark_col else ""
            hours = week_val

            records.append({
                "项目编号": project_no,
                "项目名称": project_name,
                "备注": remark,
                "工时": hours,
            })

        wb_src.close()
    finally:
        try:
            import os as _os
            _os.remove(tmp_path)
        except OSError:
            pass

    # Write the output Excel with styling (same style as _action_export_excel).
    wb_out = Workbook()
    ws_out = wb_out.active
    ws_out.title = "工时记录"
    headers = ["项目编号", "项目名称", "备注", "工时"]
    ws_out.append(headers)
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4FC3F7", end_color="4FC3F7", fill_type="solid")
    for cell in ws_out[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    if records:
        for rec in records:
            ws_out.append([rec["项目编号"], rec["项目名称"], rec["备注"], rec["工时"]])
    else:
        ws_out.append(["（暂无数据）", "", "", ""])

    for i in range(1, len(headers) + 1):
        ws_out.column_dimensions[chr(64 + i)].width = 24

    path = str(Path(ctx.artifacts_dir) / output_filename)
    wb_out.save(path)
    ctx.artifacts.append(path)
    ctx.steps.append(
        f"Excel工时导出：{output_filename}（{len(records)} 行，周次={week_label}）"
    )
    return records


# ---- Registry ----

ACTION_REGISTRY: dict[str, Callable[[dict[str, Any], PipelineContext], Any]] = {
    "ai_extract": _action_ai_extract,
    "ai_meeting_extract": _action_ai_meeting_extract,
    "ai_summarize": _action_ai_summarize,
    "ai_classify": _action_ai_classify,
    "export_excel": _action_export_excel,
    "export_json": _action_export_json,
    "export_markdown": _action_export_markdown,
    "create_task": _action_create_task,
    "excel_workload_export": _action_excel_workload_export,
    "notify": _action_notify,
}


def run_action(action_config: dict[str, Any], ctx: PipelineContext) -> Any:
    """Dispatch to the configured action and return its output."""
    action_type = action_config.get("type", "")
    params = action_config.get("params", {}) or {}
    handler = ACTION_REGISTRY.get(action_type)
    if handler is None:
        raise ValueError(f"未知的动作类型：{action_type}")
    return handler(params, ctx)
