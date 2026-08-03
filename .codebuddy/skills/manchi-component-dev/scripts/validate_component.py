#!/usr/bin/env python3
"""Validate Manchi components.

One component = one folder named by its id, containing `manifest.json`
and `component.py`.

Usage:
    python3 validate_component.py <path>
        <path> can be:
          - a single component folder (has manifest.json inside)
          - a components root dir  -> validates every subfolder component
          - a manifest.json or component.py file -> locate its folder

Exit code 0 = PASS (no errors), 1 = FAIL (errors found).
"""
from __future__ import annotations

import ast
import json
import re
import sys
import tempfile
import importlib.util
from pathlib import Path

ALLOWED_TYPES = {"transform", "output", "standalone", "source"}
ALLOWED_INPUT_REQS = {
    "none", "any", "text", "mail", "excel", "csv",
    "docx", "pdf", "json", "table", "file",
}
ALLOWED_PARAM_TYPES = {
    "string", "number", "boolean", "select", "textarea", "file",
}

NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

ERRORS: list[str] = []
WARNINGS: list[str] = []


def err(msg: str) -> None:
    ERRORS.append(msg)


def warn(msg: str) -> None:
    WARNINGS.append(msg)


def find_py(folder: Path) -> Path | None:
    cand = folder / "component.py"
    if cand.exists():
        return cand
    pys = [f for f in folder.glob("*.py") if f.name != "__init__.py"]
    return pys[0] if pys else None


def discover(root: Path) -> list[tuple[Path | None, Path]]:
    """Return list of (py_path, manifest_path) pairs."""
    if (root / "manifest.json").exists():
        return [(find_py(root), root / "manifest.json")]
    pairs: list[tuple[Path | None, Path]] = []
    if root.is_dir():
        for d in sorted(root.iterdir()):
            mj = d / "manifest.json"
            if d.is_dir() and mj.exists():
                pairs.append((find_py(d), mj))
    return pairs


def validate_manifest(mj: Path) -> dict | None:
    try:
        data = json.loads(mj.read_text(encoding="utf-8"))
    except Exception as e:
        err(f"manifest 不是合法 JSON: {e}")
        return None

    name = data.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        err("manifest.name 必须是 snake_case（小写字母开头，仅含 [a-z0-9_]）")
    if name and mj.parent.name != name:
        err(f"文件夹名 '{mj.parent.name}' 与 manifest.name '{name}' 不一致")

    if not data.get("display_name"):
        err("manifest.display_name 不能为空")
    if not data.get("description"):
        warn("manifest.description 为空，建议补充")

    ctype = data.get("type")
    if ctype not in ALLOWED_TYPES:
        err(f"manifest.type 非法: {ctype!r}（允许 {sorted(ALLOWED_TYPES)}）")

    ireq = data.get("input_requirement", "any")
    if ireq not in ALLOWED_INPUT_REQS:
        err(f"manifest.input_requirement 非法: {ireq!r}")

    params = data.get("params", {})
    if isinstance(params, list):
        err("manifest.params 必须是对象（按参数名索引 {name: {...}}），不能是数组")
    elif not isinstance(params, dict):
        err("manifest.params 必须是对象")
    else:
        for pname, pdef in params.items():
            if not isinstance(pdef, dict):
                err(f"params.{pname} 定义必须是对象")
                continue
            if "label" not in pdef:
                warn(f"params.{pname} 缺少 label（UI 显示名）")
            ptype = pdef.get("type")
            if ptype not in ALLOWED_PARAM_TYPES:
                err(f"params.{pname}.type 非法: {ptype!r}")
            if ptype == "select" and "options" not in pdef:
                err(f"params.{pname} type=select 必须提供 options 数组")

    requires = data.get("requires", [])
    if not isinstance(requires, list) or not all(isinstance(x, str) for x in requires):
        err("manifest.requires 必须是字符串数组")

    if data.get("source") not in ("system", "custom", None):
        warn("manifest.source 建议为 'system' 或 'custom'")

    return data


def validate_py(py: Path, data: dict | None = None) -> None:
    src = py.read_text(encoding="utf-8")

    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        err(f"component.py 语法错误: {e}")
        return

    run_def = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run":
            run_def = node
            break
    if run_def is None:
        err("component.py 缺少 run(params, context) 函数")
        return
    pos = [a.arg for a in run_def.args.args if a.arg not in ("self", "cls")]
    if len(pos) < 2:
        err("run() 必须至少接受 (params, context) 两个位置参数")
    if run_def.args.vararg or run_def.args.kwarg:
        warn("run() 使用了 *args/**kwargs，确认调用方能正确传参")

    # --- Top-level (module-scope) imports of heavy/3rd-party libs must be
    # declared in requires. Undeclared top-level imports crash loading when the
    # package isn't installed — the #1 cause of "component fails to run". ---
    requires = (data or {}).get("requires", []) or []
    req_norm = {
        r.split("==")[0].split(">=")[0].split("<")[0].strip().lower() for r in requires
    }
    HEAVY = {"pandas", "openpyxl", "numpy", "pdfplumber", "docx",
             "requests", "playwright"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = (alias.asname or alias.name).split(".")[0].lower()
                if mod in HEAVY and mod not in req_norm:
                    err(
                        f"模块顶层 import {alias.name}，但未在 manifest.requires 声明；"
                        f"请改为 run() 内惰性 import，或加入 requires"
                    )
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0].lower()
            if mod in HEAVY and mod not in req_norm:
                err(
                    f"模块顶层 from {node.module} import ...，但未在 manifest.requires 声明；"
                    f"请改为 run() 内惰性 import，或加入 requires"
                )

    # --- For excel/csv/table inputs the engine already parses the source into
    # list[dict]; re-reading the file is the classic runtime failure. ---
    ireq = (data or {}).get("input_requirement", "any")
    if ireq in ("excel", "csv", "table"):
        if re.search(r"pd\.read_excel\s*\(", src):
            warn("input_requirement 为 excel/csv/table 时 input_data 已是 list[dict]，"
                 "不要再 pd.read_excel(input_data)")
        if re.search(r"open\s*\(\s*input_data", src) or re.search(
                r"os\.path\.exists\s*\(\s*input_data", src):
            warn("input_requirement 为 excel/csv/table 时 input_data 已是 list[dict]，"
                 "不要把它当文件路径 open/exists")

    if re.search(r"(api[_-]?key|secret|token|password)\s*=\s*['\"][^'\"]+['\"]",
                 src, re.IGNORECASE):
        warn("检测到疑似硬编码密钥（如 api_key=\"...\"），secret 应走 params")
    if re.search(r"sk-[A-Za-z0-9]{20,}", src):
        warn("检测到疑似 API key 字面量，secret 应走 params")
    if re.search(r"(HKEY_|winreg|registry|CreateService|sc\s+create)", src, re.IGNORECASE):
        warn("检测到注册表/系统服务操作，属边界红线，需确认必要")
    if re.search(r"(os\.system|subprocess\.call|eval\(|exec\()", src):
        warn("检测到 os.system/subprocess/eval/exec，确认无注入风险")
    if re.search(r"[A-Za-z]:\\\\|/Users/|/home/", src):
        warn("检测到疑似硬编码绝对路径，应改用 context['artifacts_dir']")
    if "input_data" not in src and "context" in src:
        warn("run() 似乎未使用 context['input_data']，确认输入来源正确")

    try:
        with tempfile.TemporaryDirectory() as td:
            spec = importlib.util.spec_from_file_location("_manchi_comp", str(py))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            if not callable(getattr(mod, "run", None)):
                err("导入后 run 不可调用（见上方错误）")
    except ImportError as e:
        warn(f"导入时缺少依赖（通常有 requires 声明即可）: {e}")
    except Exception as e:  # noqa: BLE001
        err(f"导入组件时发生异常（模块无法加载）: {e}")


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python3 validate_component.py <组件文件夹 | components根目录 | manifest.json | component.py>")
        return 2

    pairs = discover(Path(sys.argv[1]))
    if not pairs:
        print("未找到组件（需包含 manifest.json 的文件夹）")
        return 1

    print(f"发现 {len(pairs)} 个组件\n")
    for py, mj in pairs:
        print(f"=== {mj.parent.name} ===")
        print(f"[检查] manifest: {mj}")
        data = validate_manifest(mj)
        if py is not None:
            print(f"[检查] py:       {py}")
            validate_py(py, data)
        else:
            err("缺少 component.py")
        print()

    print("=" * 48)
    if ERRORS:
        print(f"结果: FAIL（{len(ERRORS)} 个错误，{len(WARNINGS)} 个警告）")
        for e in ERRORS:
            print(f"  ✗ {e}")
        for w in WARNINGS:
            print(f"  ! {w}")
        return 1
    print(f"结果: PASS（{len(WARNINGS)} 个警告）")
    for w in WARNINGS:
        print(f"  ! {w}")
    print("=" * 48)
    return 0


if __name__ == "__main__":
    sys.exit(main())
