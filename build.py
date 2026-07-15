"""
Manchi 完整构建脚本
====================
1. 用 PyInstaller 编译 FastAPI 后端 → .exe
2. 用 electron-vite 构建前端
3. 用 electron-builder 打包 NSIS 安装程序

用法:
    conda run -n airun python build.py

    # 仅编译后端
    conda run -n airun python build.py --backend-only

    # 仅打包 Electron
    conda run -n airun python build.py --electron-only
"""

import subprocess
import sys
import os
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


def build_backend():
    step("[2/4] Building backend with PyInstaller")
    run([str(PYTHON), "build_backend.py"], BACKEND_DIR)


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
        build_backend()

    if not backend_only:
        build_frontend()
        package_electron()

    print(f"\n  Build complete!")
    print(f"  Installer: {FRONTEND_DIR / 'dist'}")
