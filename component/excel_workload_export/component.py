"""Read a workload Excel, filter by name, extract this week's hours, export.

Folder-component replacement for the old system action `_action_excel_workload_export`.
Parameterized: the source file, name filter and output name all come from
`params` — nothing is hardcoded (the old default person "Cheng Jia Qing" is gone;
pass `name_filter` to scope to one person, or leave it empty to export everyone).

Expected source structure ("开发资源管理.xlsx" by default):
  - Header row at row 2 (A=开发姓名, C=项目编号, D=项目名称, J=备注, K+=weekly hours)
  - Weekly columns labeled "W{iso_week:02d}-{year}" e.g. "W28-2026"
  - Summary rows prefixed with "👤" are skipped
  - Rows with no hours in the target week are skipped
The source may be locked by Excel, so we copy to a temp file first.
"""
from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


def run(params: dict, context: dict) -> list[dict[str, Any]]:
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    file_path = str(params.get("file_path", "")).strip()
    sheet_name = str(params.get("sheet_name", "周计划主表")).strip()
    name_filter = str(params.get("name_filter", "")).strip()
    output_filename = params.get("output_filename") or "工时记录.xlsx"

    if not file_path:
        raise ValueError("excel_workload_export 未配置 file_path")

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

        name_col = 1
        project_no_col = 3
        project_name_col = 4
        remark_col = 10

        records: list[dict[str, Any]] = []
        for row in ws.iter_rows(min_row=3, values_only=False):
            name_val = row[name_col - 1].value if len(row) >= name_col else None
            name_str = str(name_val).strip() if name_val is not None else ""
            if not name_str:
                continue
            if name_str.startswith("👤"):
                continue
            # Only match the target person when a filter is set.
            if name_filter and name_str != name_filter:
                continue
            week_val = row[week_col - 1].value if len(row) >= week_col else None
            if week_val is None or str(week_val).strip() == "" or week_val == 0:
                continue

            project_no = str(row[project_no_col - 1].value or "").strip() if len(row) >= project_no_col else ""
            project_name = str(row[project_name_col - 1].value or "").strip() if len(row) >= project_name_col else ""
            remark = str(row[remark_col - 1].value or "").strip() if len(row) >= remark_col else ""

            records.append({
                "项目编号": project_no,
                "项目名称": project_name,
                "备注": remark,
                "工时": week_val,
            })
        wb_src.close()
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    # Write the output Excel with styling.
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

    out_path = Path(context["artifacts_dir"]) / output_filename
    wb_out.save(str(out_path))
    return records


if __name__ == "__main__":
    import os as _os
    import tempfile

    # Build a tiny sample workbook matching the expected structure.
    from openpyxl import Workbook as _WB

    iso_year, iso_week, _ = datetime.now().isocalendar()
    wk = f"W{iso_week:02d}-{iso_year}"
    wb = _WB()
    ws = wb.active
    ws.title = "周计划主表"
    ws.append([])                       # row 1 placeholder
    ws.append(["开发姓名", "x", "项目编号", "项目名称", "x", "x", "x", "x", "x", "备注", wk])
    ws.append(["张三", "", "P1", "项目A", "", "", "", "", "", "备注A", 8])
    ws.append(["👤 合计", "", "", "", "", "", "", "", "", "", 8])
    tmp = Path(tempfile.mkdtemp()) / "sample.xlsx"
    wb.save(str(tmp))

    ctx = {"input_data": None, "artifacts_dir": tempfile.mkdtemp()}
    recs = run({"file_path": str(tmp), "name_filter": "张三"}, ctx)
    print("records:", recs)
    print("written to:", Path(ctx["artifacts_dir"]) / "工时记录.xlsx")
