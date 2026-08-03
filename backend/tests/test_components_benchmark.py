"""Benchmark: the folder-based custom components fully replace the old
system actions (export_excel / export_json / export_markdown /
excel_workload_export) and resolve through the unified run_action, so the
seed rules in routers/rules.py keep working without code changes.

Run with the Manchi runtime venv python (has openpyxl + app deps).
"""
import os
import sys
import tempfile

COMPONENTS = r"C:\Users\z0055h5c\Documents\Manchi\components"
os.environ["MANCHI_COMPONENTS"] = COMPONENTS
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.orchestrator.engine import PipelineContext
from app.services.orchestrator.actions import run_action, COMPONENT_REGISTRY


def _ctx(data):
    return PipelineContext(
        rule_id=1, rule_name="bench", artifacts_dir=tempfile.mkdtemp(),
        current_data=data,
    )


def test_custom_components_present():
    for name in ("export_excel", "export_json", "export_markdown",
                 "excel_workload_export", "excel_to_markdown"):
        assert name in COMPONENT_REGISTRY, f"{name} 未注册"
        assert COMPONENT_REGISTRY[name]["source"] == "custom", f"{name} 应为 custom"
    print("[OK] 5 个文件夹组件均已注册为 custom")


def test_export_excel():
    ctx = _ctx([{"姓名": "张三", "年龄": "28"}, {"姓名": "李四", "年龄": "35"}])
    out = run_action({"type": "export_excel", "params": {"filename": "a.xlsx"}}, ctx)
    assert os.path.exists(os.path.join(ctx.artifacts_dir, "a.xlsx")), "xlsx 未生成"
    assert out == ctx.current_data, "output 组件应透传数据"
    print("[OK] export_excel 经统一 run_action 生成 xlsx 并透传")


def test_export_json():
    ctx = _ctx([{"k": "v"}])
    out = run_action({"type": "export_json", "params": {"filename": "a.json"}}, ctx)
    assert os.path.exists(os.path.join(ctx.artifacts_dir, "a.json"))
    assert out == ctx.current_data
    print("[OK] export_json 经统一 run_action 生成 json 并透传")


def test_export_markdown():
    ctx = _ctx([{"姓名": "张三"}, {"姓名": "李四"}])
    out = run_action({"type": "export_markdown", "params": {"filename": "a.md", "title": "T"}}, ctx)
    assert os.path.exists(os.path.join(ctx.artifacts_dir, "a.md"))
    assert out == ctx.current_data
    print("[OK] export_markdown 经统一 run_action 生成 md 并透传")


def test_excel_workload_export():
    from datetime import datetime
    from openpyxl import Workbook

    iso_year, iso_week, _ = datetime.now().isocalendar()
    wk = f"W{iso_week:02d}-{iso_year}"
    wb = Workbook()
    ws = wb.active
    ws.title = "周计划主表"
    ws.append([])
    ws.append(["开发姓名", "x", "项目编号", "项目名称", "x", "x", "x", "x", "x", "备注", wk])
    ws.append(["张三", "", "P1", "项目A", "", "", "", "", "", "备注A", 8])
    ws.append(["👤 合计", "", "", "", "", "", "", "", "", "", 8])
    tmp = os.path.join(tempfile.mkdtemp(), "sample.xlsx")
    wb.save(tmp)

    ctx = PipelineContext(rule_id=1, rule_name="bench", artifacts_dir=tempfile.mkdtemp())
    recs = run_action(
        {"type": "excel_workload_export",
         "params": {"file_path": tmp, "name_filter": "张三"}}, ctx)
    assert isinstance(recs, list) and len(recs) >= 1, f"未提取到工时: {recs}"
    assert os.path.exists(os.path.join(ctx.artifacts_dir, "工时记录.xlsx"))
    print(f"[OK] excel_workload_export 经统一 run_action 提取 {len(recs)} 条并生成工时记录.xlsx")


if __name__ == "__main__":
    test_custom_components_present()
    test_export_excel()
    test_export_json()
    test_export_markdown()
    test_excel_workload_export()
    print("\n=== 全部基准测试通过：旧系统动作已被文件夹组件完全替代 ===")
