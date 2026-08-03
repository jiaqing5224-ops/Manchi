"""Verify the custom component works inside the real app env.

Uses the real Manchi components dir and the normal `app` import path
(so the full engine/sqlalchemy import chain is exercised).

The default `excel_to_markdown` component is contract-conformant:
input_requirement="excel" means the engine parses the source Excel file
into list[dict] and passes that as input_data; the component returns a
Markdown string.
"""
import os
import sys
import tempfile

from openpyxl import Workbook

COMPONENTS = r"C:\Users\z0055h5c\Documents\Manchi\components"
os.environ["MANCHI_COMPONENTS"] = COMPONENTS
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.orchestrator.engine import PipelineContext
from app.services.orchestrator.actions import run_action, COMPONENT_REGISTRY

# Build a real Excel file so the engine's excel->list[dict] parsing has input.
art = tempfile.mkdtemp()
xlsx = os.path.join(art, "sample.xlsx")
wb = Workbook()
ws = wb.active
for row in (["姓名", "年龄", "部门"], ["张三", "28", "技术部"], ["李四", "35", "市场部"]):
    ws.append(row)
wb.save(xlsx)

# Simulate a "file" source: current_data is the raw file content / path,
# and source_file_path points at the real Excel file. The engine adapts
# input_requirement="excel" by re-reading the file into list[dict].
ctx = PipelineContext(
    rule_id=1,
    rule_name="verify",
    artifacts_dir=art,
    source_type="file",
    source_file_path=xlsx,
)
ctx.current_data = xlsx

assert "excel_to_markdown" in COMPONENT_REGISTRY, list(COMPONENT_REGISTRY)
print("[OK] 真实环境已发现自定义组件 excel_to_markdown")

out = run_action({"type": "excel_to_markdown", "params": {"write_to_file": False}}, ctx)
assert isinstance(out, str), f"组件应返回 Markdown 字符串，实际: {type(out)}"
assert "| 姓名 | 年龄 | 部门 |" in out, out
print("[OK] 经统一 run_action 调用成功，返回 Markdown 表格")
print(out)
print("\n=== 组件在真实运行环境中可用 ===")
