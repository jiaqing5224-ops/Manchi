"""Test that a skill-generated component can be discovered and executed.

Point MANCHI_COMPONENTS at the folder that contains the generated component,
then verify PluginManager + the unified run_action path both work.
"""
import importlib.util
import os
import sys
import tempfile
from types import SimpleNamespace

# Point the plugin manager at the runtime components dir (where the
# skill-generated component is actually installed) before import.
COMPONENTS = r"C:\Users\z0055h5c\Documents\Manchi\components"
os.environ["MANCHI_COMPONENTS"] = COMPONENTS
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load actions.py directly (file-based) to avoid importing the orchestrator
# package __init__, which pulls heavy optional deps (sqlalchemy/pywin32) not
# installed in this lightweight test env. This still exercises the real
# run_action / COMPONENT_REGISTRY logic we changed.
_ACTIONS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "app", "services", "orchestrator", "actions.py",
)
_spec = importlib.util.spec_from_file_location("manchi_actions_test", _ACTIONS_PATH)
_actions = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_actions)
run_action = _actions.run_action
COMPONENT_REGISTRY = _actions.COMPONENT_REGISTRY

from app.services.plugin_manager import PluginManager

SAMPLE = [
    {"姓名": "张三", "年龄": "28", "部门": "技术部"},
    {"姓名": "李四", "年龄": "35", "部门": "市场部"},
    {"姓名": "王五", "年龄": "42", "部门": "财务部"},
]


def test_plugin_manager_direct():
    pm = PluginManager(COMPONENTS)
    discovered = pm.discover_components()
    assert "excel_to_markdown" in discovered, f"未发现在组件: {list(discovered)}"
    print("[PM] 发现组件:", list(discovered))

    md = pm.run_component(
        "excel_to_markdown",
        {"write_to_file": False, "columns": "姓名,部门"},
        {"input_data": SAMPLE, "artifacts_dir": tempfile.gettempdir()},
    )
    print("[PM] 运行结果:\n" + md)
    assert "| 姓名 | 部门 |" in md
    assert "年龄" not in md  # 列过滤生效
    print("[PM] PASS: 组件可被直接加载并运行\n")


def test_unified_run_action():
    # COMPONENT_REGISTRY 在 import actions 时已 refresh，应包含 excel_to_markdown
    assert "excel_to_markdown" in COMPONENT_REGISTRY, (
        "统一注册表未包含自定义组件: " + str(list(COMPONENT_REGISTRY))
    )
    print("[REG] 注册表中的组件数:", len(COMPONENT_REGISTRY))
    print("[REG] 自定义组件:", [n for n, e in COMPONENT_REGISTRY.items()
                                 if e["source"] == "custom"])

    ctx = SimpleNamespace(
        rule_id=1, rule_name="test", artifacts_dir=tempfile.gettempdir(),
        current_data=SAMPLE, source_type="", source_content="",
        source_file_path="", db=None,
    )

    out = run_action(
        {"type": "excel_to_markdown",
         "params": {"write_to_file": True, "output_filename": "out.md"}},
        ctx,
    )
    print("[REG] run_action 结果:\n" + out)
    assert "| 姓名 | 年龄 | 部门 |" in out  # 全列
    # 文件已写入 artifacts_dir
    written = os.path.join(tempfile.gettempdir(), "out.md")
    assert os.path.exists(written), "write_to_file 未产出文件"
    print("[REG] PASS: 经统一 run_action 调用成功，产物已写入\n")
    os.remove(written)


if __name__ == "__main__":
    test_plugin_manager_direct()
    test_unified_run_action()
    print("=== 全部测试通过：skill 生成的组件可被系统直接使用 ===")
