"""Pipeline input sources — mail / text / file.

Each source fetches raw data according to its config and writes it into the
PipelineContext. The data shape is source-specific:

  - mail  → list[OutlookMail]
  - text  → str
    - file  → str (text file content, or Excel workbook converted to text)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from openpyxl import load_workbook

from app.services.orchestrator.engine import PipelineContext

logger = logging.getLogger(__name__)


def _fetch_mail(config: dict[str, Any], ctx: PipelineContext) -> list[Any]:
    """Scan Outlook inbox for the last N days, optionally filtered by sender."""
    from app.services.outlook.mail_handler import scan_inbox_range

    days = int(config.get("days_range", 5))
    sender_filter = str(config.get("sender_filter", "")).strip().lower()

    end = datetime.now()
    start = end - timedelta(days=days)
    mails = scan_inbox_range(start, end)
    if sender_filter:
        mails = [m for m in mails if sender_filter in (m.sender_email or "").lower()
                 or sender_filter in (m.sender_name or "").lower()]
    ctx.steps.append(f"邮件源：扫描 {len(mails)} 封邮件（最近 {days} 天）")
    return list(mails)


def _fetch_text(config: dict[str, Any], ctx: PipelineContext) -> str:
    """Return the user-supplied custom text."""
    content = str(config.get("content", ""))
    ctx.steps.append(f"文本源：{len(content)} 字符")
    return content


def _fetch_file(config: dict[str, Any], ctx: PipelineContext) -> str:
    """Read a local file as text, converting Excel workbooks to text tables."""
    file_path = str(config.get("file_path", "")).strip()
    encoding = str(config.get("encoding", "utf-8"))
    if not file_path:
        raise ValueError("文件源未配置 file_path")
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"文件不存在：{file_path}")
    suffix = Path(file_path).suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        content = _read_excel_as_text(file_path)
        ctx.steps.append(f"文件源：读取 Excel {Path(file_path).name}（{len(content)} 字符）")
        return content
    if suffix == ".xls":
        raise ValueError("暂不支持旧版 .xls 文件，请另存为 .xlsx 后再选择")
    with open(file_path, "r", encoding=encoding, errors="replace") as f:
        content = f.read()
    ctx.steps.append(f"文件源：读取 {Path(file_path).name}（{len(content)} 字符）")
    return content


def _read_excel_as_text(file_path: str) -> str:
    workbook = load_workbook(file_path, data_only=True, read_only=True)
    sections: list[str] = []
    try:
        for sheet in workbook.worksheets:
            rows: list[str] = []
            for row in sheet.iter_rows(values_only=True):
                values = ["" if cell is None else str(cell) for cell in row]
                if any(value.strip() for value in values):
                    rows.append("\t".join(values).rstrip())
            if rows:
                sections.append(f"# Sheet: {sheet.title}\n" + "\n".join(rows))
    finally:
        workbook.close()
    return "\n\n".join(sections)


SOURCE_REGISTRY: dict[str, Callable[[dict[str, Any], PipelineContext], Any]] = {
    "mail": _fetch_mail,
    "text": _fetch_text,
    "file": _fetch_file,
}


def fetch_source(config: dict[str, Any], ctx: PipelineContext) -> Any:
    """Dispatch to the configured source and return its raw output."""
    source_type = config.get("type", "text")
    handler = SOURCE_REGISTRY.get(source_type)
    if handler is None:
        raise ValueError(f"未知的输入源类型：{source_type}")
    return handler(config, ctx)
