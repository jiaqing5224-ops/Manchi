"""
Manchi 完整构建脚本
====================
1. 准备可移植的 CPython 运行时（复制到 backend/dist/python，供首次启动
   时 bootstrap 出专用 venv 使用）
2. 用 electron-vite 构建前端
3. 用 electron-builder 打包 NSIS 安装程序

说明: 后端不再用 PyInstaller 冻结成 exe，而是以源码形式打包，运行时通过一个
专用的、用户可写的 venv（见 electron/main/backend.ts +
backend/scripts/bootstrap_runtime.py）来启动，这样才能在运行时 pip install
组件依赖。

用法:
    conda run -n airun python build.py

    # 仅打包 Electron
    conda run -n airun python build.py --electron-only
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend" / "manchi-ui"
PYTHON = os.environ.get("MANCHI_PYTHON", sys.executable)


def step(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def run(cmd: list[str], cwd: Path, env: dict | None = None):
    print(f"  > {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(cmd, cwd=cwd, shell=True, env=env)
    if result.returncode != 0:
        print(f"  FAILED (exit code {result.returncode})")
        sys.exit(1)


def setup_cache():
    step("[1/4] Setting up build cache (winCodeSign, NSIS)")
    run([str(PYTHON), "setup_build_cache.py"], ROOT)

    # Copy project cache to system cache (where app-builder looks for it)
    project_cache = ROOT / ".build-cache" / "electron-builder"
    sys_cache = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "electron-builder" / "Cache"
    if project_cache.exists():
        print(f"  Copying project cache to: {sys_cache}")
        import shutil
        for src_dir in project_cache.iterdir():
            if src_dir.is_dir():
                dst = sys_cache / src_dir.name
                dst.mkdir(parents=True, exist_ok=True)
                for item in src_dir.iterdir():
                    if item.is_dir():
                        shutil.copytree(item, dst / item.name, dirs_exist_ok=True)


def stage_runtime_python():
    """Copy a full standard CPython into backend/dist/python.

    The first-launch bootstrap (bootstrap_runtime.py) builds the runtime venv
    from this copy, so clean machines without a system Python can still
    bootstrap. We copy a full install (which includes pip + venv + ensurepip),
    not the embeddable zip (which lacks pip). Optional bloat is pruned.
    """
    step("[2/4] Staging portable Python runtime")

    src = os.environ.get("MANCHI_BUNDLE_PYTHON")
    if not src:
        cand = Path(r"C:\Program Files\Python311")
        if cand.exists():
            src = str(cand)
        else:
            for d in sorted(Path(r"C:\Program Files").glob("Python3*"), reverse=True):
                if (d / "python.exe").exists():
                    src = str(d)
                    break

    dst = BACKEND_DIR / "dist" / "python"
    if not src:
        print("  [WARN] No standard CPython found under C:\\Program Files\\Python3*.")
        print("  [WARN] Skipping bundling; clean machines without a system Python")
        print("  [WARN] will be unable to bootstrap the runtime.")
        return

    src = Path(src)
    if not (src / "python.exe").exists():
        print(f"  [ERROR] BUNDLE source has no python.exe: {src}")
        sys.exit(1)

    if dst.exists():
        shutil.rmtree(dst)
    print(f"  Staging from: {src}")

    # Prune optional/large directories that are not needed at runtime.
    # (Lib/site-packages is excluded: the venv gets its own from requirements.txt,
    #  and python -m venv / bootstrap_runtime.py only need the stdlib.)
    prune = {"Lib/test", "Lib/tkinter", "Lib/idlelib", "Lib/site-packages",
             "tcl", "Tools", "Doc", "include"}

    def ignore(path, names):
        rel = os.path.relpath(path, str(src))
        ignored = set()
        for n in names:
            full = os.path.join(path, n)
            if os.path.isdir(full):
                key = os.path.join(rel, n) if rel != "." else n
                if key in prune:
                    ignored.add(n)
        return ignored

    shutil.copytree(src, dst, ignore=ignore, symlinks=False, dirs_exist_ok=True)
    print(f"  Portable Python staged at: {dst}")


def build_frontend():
    step("[3/4] Building frontend with electron-vite")
    run("npx electron-vite build", FRONTEND_DIR)


def package_electron():
    step("[4/4] Packaging with electron-builder")
    env = os.environ.copy()
    env["CSC_IDENTITY_AUTO_DISCOVERY"] = "false"  # 跳过代码签名
    run("npx electron-builder build --win --config electron-builder.yml", FRONTEND_DIR)


if __name__ == "__main__":
    backend_only = "--backend-only" in sys.argv
    electron_only = "--electron-only" in sys.argv

    if not electron_only:
        setup_cache()
        stage_runtime_python()

    if not backend_only:
        build_frontend()
        package_electron()

    print(f"\n  Build complete!")
    print(f"  Installer: {FRONTEND_DIR / 'dist'}")
