"""
Build the Manchi backend into a standalone executable using PyInstaller.

Usage:
    conda run -n airun python build_backend.py

Output:
    backend/dist/manchi-backend/
        manchi-backend.exe    # The backend executable
        ... (supporting DLLs and .pyd files)

The resulting directory will be bundled by electron-builder as extraResources.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.resolve()
DIST_DIR = BACKEND_DIR / "dist"
BUILD_DIR = BACKEND_DIR / "build"
SPEC_FILE = BACKEND_DIR / "manchi-backend.spec"

# Clean previous builds
if DIST_DIR.exists():
    shutil.rmtree(DIST_DIR)
if BUILD_DIR.exists():
    shutil.rmtree(BUILD_DIR)

# ── Hidden imports that PyInstaller might miss ─────────────────────
HIDDEN_IMPORTS = [
    # FastAPI / uvicorn
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    # App modules
    "app.routers",
    "app.models",
    "app.schemas",
    "app.services",
    "app.services.llm",
    "app.services.outlook",
    # SQLAlchemy
    "sqlalchemy.sql.default_comparator",
    # pydantic
    "pydantic",
    "pydantic_settings",
]

# ── Conda DLLs that PyInstaller can't find automatically ──────────
CONDA_LIB_BIN = Path(sys.executable).parent / "Library" / "bin"
MISSING_DLLS = ["libexpat.dll", "liblzma.dll", "libbz2.dll", "ffi-8.dll", "sqlite3.dll"]

# ── Run PyInstaller ────────────────────────────────────────────────
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--name", "manchi-backend",
    "--onedir",                       # Directory output (faster startup than onefile)
    "--distpath", str(DIST_DIR),
    "--workpath", str(BUILD_DIR),
    "--add-data", f"{BACKEND_DIR / 'app'};app",
]

# Explicitly include missing conda DLLs
for dll in MISSING_DLLS:
    dll_path = CONDA_LIB_BIN / dll
    if dll_path.exists():
        cmd.extend(["--add-binary", f"{dll_path};."])

cmd.extend([
    "--hidden-import", "uvicorn.logging",
    "--hidden-import", "uvicorn.loops.auto",
    "--hidden-import", "uvicorn.protocols.http.auto",
    "--hidden-import", "pyexpat",
    "--collect-submodules", "app",
    "--collect-data", "uvicorn",
    "--collect-data", "fastapi",
])

for mod in HIDDEN_IMPORTS:
    cmd.extend(["--hidden-import", mod])

cmd.append(str(BACKEND_DIR / "run_backend.py"))

print("Building Manchi backend with PyInstaller...")
print(f"Command: {' '.join(cmd)}")

# Add conda Library/bin to PATH so PyInstaller can find DLLs
env = os.environ.copy()
env["PATH"] = f"{CONDA_LIB_BIN};{env['PATH']}"
subprocess.check_call(cmd, env=env)

# ── Verify ─────────────────────────────────────────────────────────
exe_path = DIST_DIR / "manchi-backend" / "manchi-backend.exe"
if exe_path.exists():
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"\nBuild successful!")
    print(f"  Executable: {exe_path}")
    print(f"  Size: {size_mb:.1f} MB")
    print(f"\nTotal directory size:")
    total_kb = sum(f.stat().st_size for f in (DIST_DIR / "manchi-backend").rglob("*")) / 1024
    print(f"  {total_kb / 1024:.1f} MB")
else:
    print(f"\nBuild FAILED - executable not found at {exe_path}")
    sys.exit(1)
