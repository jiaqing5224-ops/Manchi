"""Render pipeline data as a Markdown document and write it to artifacts_dir.

Folder-component replacement for the old system action `_action_export_markdown`
plus its `_to_markdown` helper (rendering logic ported below). Returns the input
data unchanged so the chain can continue.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _to_markdown(data: Any, title: str = "") -> str:
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


def run(params: dict, context: dict) -> Any:
    title = str(params.get("title", "")).strip()
    filename = params.get("filename") or f"导出_{datetime.now():%Y%m%d_%H%M%S}.md"
    text = _to_markdown(context.get("input_data"), title)
    out = Path(context["artifacts_dir"]) / filename
    out.write_text(text, encoding="utf-8")
    return context.get("input_data")


if __name__ == "__main__":
    import tempfile

    sample = [{"姓名": "张三", "年龄": "28"}, {"姓名": "李四", "年龄": "35"}]
    ctx = {"input_data": sample, "artifacts_dir": tempfile.mkdtemp()}
    out = run({"title": "示例", "filename": "demo.md"}, ctx)
    print("returned items:", len(out))
    print("written to:", Path(ctx["artifacts_dir"]) / "demo.md")
