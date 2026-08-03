"""Export pipeline data (list[dict]) to a styled Excel file in artifacts_dir.

This is the folder-based replacement for the old system action
`_action_export_excel`. It is a pure output component: it writes a file and
returns the input data unchanged so the chain can continue.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def run(params: dict, context: dict) -> Any:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    data = context.get("input_data")
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
    out = Path(context["artifacts_dir"]) / filename
    wb.save(str(out))
    return data


if __name__ == "__main__":
    import tempfile

    sample = [
        {"姓名": "张三", "年龄": "28", "部门": "技术部"},
        {"姓名": "李四", "年龄": "35", "部门": "市场部"},
    ]
    ctx = {"input_data": sample, "artifacts_dir": tempfile.mkdtemp()}
    out = run({"filename": "demo.xlsx"}, ctx)
    print("returned rows:", len(out))
    print("written to:", Path(ctx["artifacts_dir"]) / "demo.xlsx")
