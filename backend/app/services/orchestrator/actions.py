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

from typing import TYPE_CHECKING

from app.services.plugin_manager import PluginManager
from app.services.llm.client import chat_complete, get_llm_settings

if TYPE_CHECKING:
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

def _ai_result_to_markdown(result: Any, mode: str) -> str:
    """Render an AI action result as a markdown string.

    - summarize returns prose (str) -> returned as-is (markdown renders plain
      text fine).
    - extract/classify return list[dict] -> rendered as a markdown table.
    """
    if isinstance(result, str):
        return result
    if not isinstance(result, list) or not result:
        return "_（无内容）_"
    headers: list[str] = []
    for item in result:
        if isinstance(item, dict):
            for k in item:
                if k not in headers:
                    headers.append(k)
    if not headers:
        return "\n".join(f"- {item}" for item in result)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for item in result:
        if isinstance(item, dict):
            lines.append("| " + " | ".join(str(item.get(h, "")) for h in headers) + " |")
        else:
            lines.append(f"| {item} |")
    return "\n".join(lines)


def _action_ai_analyze(params: dict[str, Any], ctx: PipelineContext) -> Any:
    """Unified AI analysis action: extract / summarize / classify.

    params:
      mode: "extract" | "summarize" | "classify" (default "extract")
      output_format: "raw" | "markdown" (default "raw")
        - raw: returns list[dict] for extract/classify, str for summarize.
               This is the backward-compatible shape consumed by create_task
               and the export_* components.
        - markdown: always returns a markdown string suitable for display.

    The three legacy actions (ai_extract / ai_summarize / ai_classify) are thin
    aliases that call this with a fixed mode + output_format=raw, so existing
    seed rules keep working unchanged.
    """
    from app.services.llm.client import chat_complete

    mode = str(params.get("mode", "extract")).strip().lower()
    output_format = str(params.get("output_format", "raw")).strip().lower()

    text_input = _to_text(ctx.current_data)
    if not text_input:
        ctx.steps.append(f"AI分析({mode})：输入为空，跳过")
        return [] if mode in ("extract", "classify") else ""

    try:
        if mode == "extract":
            fields = params.get("fields", [])
            if isinstance(fields, str):
                fields = [f.strip() for f in fields.split(",") if f.strip()]
            prompt_extra = str(params.get("prompt_extra", "")).strip()
            fields_desc = "、".join(fields) if fields else "相关信息"
            prompt = (
                f"你是信息提取助手。从下面的文本中提取以下字段：{fields_desc}。\n"
                f"返回 JSON 数组，每个元素是一个对象，包含这些字段（无法判断的字段填 null）。\n"
                f"只返回 JSON 数组，不要多余文字。\n\n"
                f"{prompt_extra}\n\n文本：\n{text_input}"
            )
            raw = chat_complete([], prompt, temperature=0.0)
            result = _parse_llm_json(raw)
            if not isinstance(result, list):
                result = [result] if isinstance(result, dict) else []
            ctx.steps.append(f"AI分析：提取到 {len(result)} 条结构化记录")

        elif mode == "classify":
            categories = params.get("categories", ["常规"])
            if isinstance(categories, str):
                categories = [c.strip() for c in categories.split(",") if c.strip()]
            cats_desc = "、".join(categories)
            prompt = (
                f"你是分类助手。将下面的每条内容归入以下类别之一：{cats_desc}。\n"
                f"返回 JSON 数组，每个元素格式：{{\"index\": int, \"tag\": \"类别\", \"reason\": \"简短理由\"}}。\n"
                f"只返回 JSON 数组。\n\n内容：\n{text_input}"
            )
            raw = chat_complete([], prompt, temperature=0.0)
            result = _parse_llm_json(raw)
            if not isinstance(result, list):
                result = [result] if isinstance(result, dict) else []
            ctx.steps.append(f"AI分析：分类 {len(result)} 条")

        elif mode == "summarize":
            max_length = int(params.get("max_length", 300))
            prompt = (
                f"请用中文对下面的内容生成一份不超过 {max_length} 字的摘要，"
                f"突出关键信息，条理清晰：\n\n{text_input}"
            )
            result = chat_complete([], prompt, temperature=0.3)
            ctx.steps.append(f"AI分析：生成 {len(result)} 字摘要")

        else:
            ctx.steps.append(f"AI分析：未知模式 {mode}，跳过")
            return [] if mode in ("extract", "classify") else ""
    except Exception as e:
        logger.error("ai_analyze(%s) failed: %s", mode, e)
        ctx.steps.append(f"AI分析：失败 ({e})")
        return [] if mode in ("extract", "classify") else ""

    if output_format == "markdown":
        return _ai_result_to_markdown(result, mode)
    return result


def _action_ai_extract(params: dict[str, Any], ctx: PipelineContext) -> list[dict[str, Any]]:
    """Backward-compatible alias -> ai_analyze(mode=extract, output_format=raw)."""
    p = dict(params)
    p["mode"] = "extract"
    p["output_format"] = "raw"
    return _action_ai_analyze(p, ctx)


def _action_ai_summarize(params: dict[str, Any], ctx: PipelineContext) -> str:
    """Backward-compatible alias -> ai_analyze(mode=summarize, output_format=raw)."""
    p = dict(params)
    p["mode"] = "summarize"
    p["output_format"] = "raw"
    return _action_ai_analyze(p, ctx)


def _action_ai_classify(params: dict[str, Any], ctx: PipelineContext) -> list[dict[str, Any]]:
    """Backward-compatible alias -> ai_analyze(mode=classify, output_format=raw)."""
    p = dict(params)
    p["mode"] = "classify"
    p["output_format"] = "raw"
    return _action_ai_analyze(p, ctx)


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


def _action_notify(params: dict[str, Any], ctx: PipelineContext) -> Any:
    """Record a notification step (no-op stub for now — tray notification later)."""
    message = str(params.get("message", "编排执行完成"))
    ctx.steps.append(f"通知：{message}")
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


# ---- Registry ----

ACTION_REGISTRY: dict[str, Callable[[dict[str, Any], PipelineContext], Any]] = {
    "ai_analyze": _action_ai_analyze,
    "ai_extract": _action_ai_extract,
    "ai_meeting_extract": _action_ai_meeting_extract,
    "ai_summarize": _action_ai_summarize,
    "ai_classify": _action_ai_classify,
    "create_task": _action_create_task,
    "notify": _action_notify,
}

# Unified registry: system actions + on-disk custom components.
# Each entry: {"handler": callable(params, ctx), "source": str, "manifest": dict}
COMPONENT_REGISTRY: dict[str, dict] = {}

_plugin_manager = PluginManager()


def _ctx_to_dict(ctx: PipelineContext) -> dict:
    """Adapt a PipelineContext to the dict contract custom components expect."""
    return {
        "input_data": ctx.current_data,
        "artifacts_dir": ctx.artifacts_dir,
        "source_type": ctx.source_type,
        "source_content": ctx.source_content,
        "source_file_path": ctx.source_file_path,
        "db": ctx.db,
        "artifacts": ctx.artifacts,
        "llm_call": _component_llm_call,
        "make_llm": _component_make_llm,
        "add_artifact": ctx.artifacts.append,
    }


def _component_llm_call(
    prompt: str,
    history: list[dict] | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> str:
    """LLM call exposed to custom components.

    Mirrors the skill contract ``context["llm_call"](prompt, history, ...)`` and
    routes through the user-configured LLM endpoint in settings.json.
    """
    return chat_complete(history or [], prompt, temperature=temperature, max_tokens=max_tokens)


def _component_make_llm(temperature: float = 0.0, max_tokens: int = 4096):
    """Return a LangChain chat model built from the configured LLM settings.

    Used by web-automation components (e.g. browser-use) that need a LangChain
    ``BaseChatModel`` rather than a raw text call. Raises a clear error if the
    LLM is not configured or the required package is missing.
    """
    cfg = get_llm_settings()
    endpoint = (cfg.get("endpoint") or "").strip()
    api_key = (cfg.get("api_key") or "").strip()
    model = (cfg.get("model") or "").strip()
    if not endpoint or not api_key or not model:
        raise RuntimeError(
            "请先在设置页配置 LLM（接口地址 / API Key / 模型）后再使用需要 LLM 的组件"
        )

    api_format = cfg.get("api_format") or "openai_chat_completions"
    base_url = endpoint.rstrip("/")
    for suffix in ("/chat/completions",):
        if base_url.endswith(suffix):
            base_url = base_url[: -len(suffix)]

    if api_format == "anthropic_messages":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("缺少依赖 langchain-anthropic，请先安装") from exc
        return ChatAnthropic(
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("缺少依赖 langchain-openai，请先安装") from exc
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _custom_handler(name: str):
    def _handler(params: dict, ctx: PipelineContext) -> Any:
        return _plugin_manager.run_component(name, params, _ctx_to_dict(ctx))

    return _handler


def refresh_components() -> None:
    """Rebuild COMPONENT_REGISTRY from system actions + discovered components."""
    COMPONENT_REGISTRY.clear()
    for name, handler in ACTION_REGISTRY.items():
        COMPONENT_REGISTRY[name] = {
            "handler": handler,
            "source": "system",
            "manifest": {"name": name, "source": "system", "type": "transform"},
        }
    for name, meta in _plugin_manager.discover_components().items():
        COMPONENT_REGISTRY[name] = {
            "handler": _custom_handler(name),
            "source": "custom",
            "manifest": meta,
        }


def _to_records(data: Any, ctx: "PipelineContext") -> Any:
    """Normalize arbitrary upstream data into list[dict] records.

    - already a list -> returned as-is (component accepts list[dict] or list[list])
    - Excel/CSV file source -> re-read the original workbook into records
    - otherwise -> best-effort parse of delimited text into records
    """
    if isinstance(data, list):
        return data
    if isinstance(data, str):
        fp = getattr(ctx, "source_file_path", "") or ""
        if fp and Path(fp).suffix.lower() in (".xlsx", ".xlsm", ".xls"):
            from app.services.orchestrator.sources import read_excel_as_records
            return read_excel_as_records(fp)
        return _parse_delimited_text_as_records(data)
    return data


def _parse_delimited_text_as_records(text: str) -> list[dict]:
    """Parse "# Sheet: ...\\n" + tab/comma-separated rows into list[dict]."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    start = 0
    while start < len(lines) and lines[start].lstrip().startswith("#"):
        start += 1
    if start >= len(lines):
        return []

    def split_row(line: str) -> list[str]:
        if "\t" in line:
            return [c.strip() for c in line.split("\t")]
        if "," in line:
            return [c.strip() for c in line.split(",")]
        return [line.strip()]

    header = split_row(lines[start])
    records: list[dict] = []
    for line in lines[start + 1:]:
        cells = split_row(line)
        if not any(cells):
            continue
        records.append(
            {header[i]: (cells[i] if i < len(cells) else "") for i in range(len(header))}
        )
    return records


def _adapt_input(data: Any, requirement: str, ctx: "PipelineContext") -> Any:
    """Adapt upstream data to the shape a component declares via input_requirement.

    Per the component spec, parsing (mail/Excel/docx/pdf ...) is a built-in source
    capability — components only declare what shape they need; the engine performs
    the adaptation here before handing data to the component.
    """
    if requirement in ("excel", "table", "csv"):
        return _to_records(data, ctx)
    if requirement == "text":
        if isinstance(data, str):
            return data
        if isinstance(data, (list, dict)):
            return json.dumps(data, ensure_ascii=False, default=str)
        return str(data)
    if requirement == "json":
        if isinstance(data, str):
            try:
                return json.loads(data)
            except Exception:
                return data
        return data
    if requirement == "file":
        fp = getattr(ctx, "source_file_path", "") or ""
        if fp:
            return fp
        return data if isinstance(data, str) else str(data)
    # none / any / mail / docx / pdf -> unchanged
    return data


def run_action(action_config: dict[str, Any], ctx: PipelineContext) -> Any:
    """Dispatch to the configured action/component and return its output."""
    action_type = action_config.get("type", "")
    params = action_config.get("params", {}) or {}
    entry = COMPONENT_REGISTRY.get(action_type)
    if entry is None:
        raise ValueError(f"未知的动作类型：{action_type}")
    manifest = entry.get("manifest") or {}
    requirement = manifest.get("input_requirement")
    if requirement and requirement not in ("any", "none"):
        ctx.current_data = _adapt_input(ctx.current_data, requirement, ctx)
    return entry["handler"](params, ctx)


refresh_components()

