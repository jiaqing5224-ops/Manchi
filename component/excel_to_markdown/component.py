"""
Excel 转 Markdown - 将上游解析的 Excel 数据转换为 Markdown 表格

Component type: transform
Input requirement: excel
Output: Markdown 格式的表格文本（字符串）
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def run(params: dict, context: dict) -> Any:
    """将 Excel 数据转换为 Markdown 表格。

    Args:
        params: {
            write_to_file:  是否同时写入 artifacts_dir (boolean, 默认 false)
            output_filename: 写入时的文件名 (string, 默认 "excel_output.md")
            columns:        要包含的列，逗号分隔。留空则包含全部 (string, 默认 "")
        }
        context: {
            input_data:    上游解析后的 Excel 数据（list[dict]）
            artifacts_dir: 产物输出目录
        }

    Returns:
        Markdown 表格字符串；若 write_to_file=true 也写入 artifacts_dir。
    """
    data = context.get("input_data")

    if not data:
        return ""

    # 校验输入格式
    if not isinstance(data, list):
        raise TypeError(f"input_data 需为 list[dict]，收到 {type(data).__name__}")

    # 取参
    write_to_file = params.get("write_to_file", False)
    output_filename = params.get("output_filename", "excel_output.md")
    columns_filter = params.get("columns", "")

    # 提取行数据（每行应为 dict）
    rows = []
    for row in data:
        if isinstance(row, dict):
            rows.append(row)
        elif isinstance(row, (list, tuple)):
            # 如果上游传的是 list，用第一行作为 header
            rows.append(row)

    if not rows:
        return ""

    # 确定列
    if isinstance(rows[0], dict):
        all_columns = list(rows[0].keys())
    else:
        all_columns = [str(i) for i in range(len(rows[0]))]

    if columns_filter:
        selected = [c.strip() for c in columns_filter.split(",") if c.strip()]
        columns = [c for c in selected if c in all_columns]
    else:
        columns = all_columns

    # 构建 Markdown 表格
    lines: list[str] = []

    # 表头
    header = "| " + " | ".join(columns) + " |"
    lines.append(header)

    # 分隔行
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    lines.append(separator)

    # 数据行
    for row in rows:
        if isinstance(row, dict):
            values = [str(row.get(col, "")) for col in columns]
        else:
            values = [str(row[i]) if i < len(row) else "" for i in range(len(columns))]
        line = "| " + " | ".join(values) + " |"
        lines.append(line)

    markdown = "\n".join(lines)

    # 写入文件
    if write_to_file:
        artifacts_dir = Path(context["artifacts_dir"])
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        out_path = artifacts_dir / output_filename
        out_path.write_text(markdown, encoding="utf-8")

    return markdown


if __name__ == "__main__":
    # 自测：模拟上游解析后的 Excel 数据
    sample_data = [
        {"姓名": "张三", "年龄": "28", "部门": "技术部"},
        {"姓名": "李四", "年龄": "35", "部门": "市场部"},
        {"姓名": "王五", "年龄": "42", "部门": "财务部"},
    ]
    sample_context = {
        "input_data": sample_data,
        "artifacts_dir": "/tmp",
    }
    result = run(
        {
            "write_to_file": False,
            "columns": "姓名,部门",
        },
        sample_context,
    )
    print(result)
    print("---")
    print("自测通过")
