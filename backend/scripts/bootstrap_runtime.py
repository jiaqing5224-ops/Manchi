"""First-launch runtime bootstrap for the Manchi backend.

Creates (if missing) a dedicated, user-writable Python virtualenv at
``<components_dir>/../venv`` and installs the backend base requirements plus
any component-declared requirements.

Why this exists
--------------
The shipped product must be able to ``pip install`` component dependencies at
runtime. A PyInstaller-frozen executable cannot receive ``pip install`` (it is
a frozen, read-only bundle), so the backend is instead run through this venv.
Dependencies therefore land in a persistent, user-writable location
(``~/Documents/Manchi/venv``) rather than inside the app install dir.

Idempotent & resumable: safe to call on every launch. If the venv already
exists and can import ``fastapi``/``uvicorn``, it returns immediately.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_base_python() -> str | None:
    """Locate a Python interpreter to build the venv from, on PATH."""
    for cand in ("py.exe", "python.exe", "python3", "python"):
        found = shutil.which(cand)
        if found:
            return found
    return None


def venv_python_path(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def ensure_runtime(
    components_dir: str,
    backend_dir: str,
    base_python: str | None = None,
) -> str:
    """Ensure the dedicated venv exists and has backend deps installed.

    Returns the path to the venv's python interpreter.
    """
    comp = Path(components_dir)
    venv = comp.parent / "venv"
    vpy = venv_python_path(venv)

    # Fast path: venv already built and importable.
    if vpy.exists():
        chk = subprocess.run(
            [str(vpy), "-c", "import fastapi, uvicorn"],
            capture_output=True,
        )
        if chk.returncode == 0:
            print(f"[bootstrap] runtime already ready: {vpy}")
            return str(vpy)

    # Need to build / repair the venv.
    base = (
        base_python
        or os.environ.get("MANCHI_BASE_PYTHON")
        or find_base_python()
    )
    if not base:
        raise RuntimeError(
            "找不到可用于创建运行时的 Python："
            "请在安装包中自带 Python，或通过 MANCHI_BASE_PYTHON 指定。"
        )

    print(f"[bootstrap] creating venv at {venv} (base: {base})")
    venv.mkdir(parents=True, exist_ok=True)
    if not vpy.exists():
        subprocess.run([base, "-m", "venv", str(venv)], check=True)

    # Upgrade pip first so later installs are reliable.
    subprocess.run(
        [str(vpy), "-m", "pip", "install", "--upgrade", "pip"],
        check=False,
    )

    req_files = [
        Path(backend_dir) / "requirements.txt",
        comp / "requirements.txt",
    ]
    for req in req_files:
        if req.exists():
            print(f"[bootstrap] installing {req}")
            subprocess.run(
                [str(vpy), "-m", "pip", "install", "-r", str(req)],
                check=False,
            )

    # Sanity gate: the backend must be importable.
    chk = subprocess.run(
        [str(vpy), "-c", "import fastapi, uvicorn"],
        capture_output=True,
    )
    if chk.returncode != 0:
        raise RuntimeError("运行时基础依赖安装失败，请查看上方 pip 输出")

    print(f"[bootstrap] runtime ready: {vpy}")
    return str(vpy)


def main() -> None:
    p = argparse.ArgumentParser(description="Manchi backend runtime bootstrap")
    p.add_argument("--components-dir", required=True)
    p.add_argument("--backend-dir", required=True)
    p.add_argument("--base-python", default=None)
    args = p.parse_args()
    ensure_runtime(args.components_dir, args.backend_dir, args.base_python)


if __name__ == "__main__":
    main()
