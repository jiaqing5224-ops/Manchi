"""
Manchi 构建缓存工具
====================
首轮运行时联网下载所有构建依赖（winCodeSign、NSIS 等），
存储在项目目录下的 .build-cache/ 中。
之后每次构建直接使用本地缓存，完全离线。

用法:
    # 首次：联网下载缓存
    conda run -n airun python setup_build_cache.py

    # 之后构建时自动使用本地缓存，不再联网
    conda run -n airun python build.py

缓存目录: .build-cache/electron-builder/
"""

import hashlib
import shutil
import subprocess
import sys
import os
import tempfile
from pathlib import Path

# ── 项目本地缓存目录（可 gitignore） ──────────────────────────────
ROOT = Path(__file__).parent.resolve()
CACHE_DIR = ROOT / ".build-cache" / "electron-builder"

# 需要下载的工具
TOOLS = {
    "winCodeSign": {
        "url": "https://github.com/electron-userland/electron-builder-binaries/releases/download/winCodeSign-2.6.0/winCodeSign-2.6.0.7z",
        "cache_key": "winCodeSign",
    },
    "nsis": {
        "url": "https://github.com/electron-userland/electron-builder-binaries/releases/download/nsis-3.0.4.1/nsis-3.0.4.1.7z",
        "cache_key": "nsis",
    },
    "nsis-resources": {
        "url": "https://github.com/electron-userland/electron-builder-binaries/releases/download/nsis-resources-3.4.1/nsis-resources-3.4.1.7z",
        "cache_key": "nsis-resources",
    },
}

# Locate 7za.exe from node_modules (preferred) or fall back to system 7z
_node_modules_7za = ROOT / "frontend" / "manchi-ui" / "node_modules" / "7zip-bin" / "win" / "x64" / "7za.exe"
SEVEN_ZIP = str(_node_modules_7za) if _node_modules_7za.exists() else "7z"


def get_cache_dir(tool: str, url: str) -> Path:
    """Compute the cache subdirectory from the URL hash (matches app-builder)."""
    url_hash = hashlib.sha256(url.lower().encode()).hexdigest()
    return CACHE_DIR / tool / url_hash


def download(url: str, dest: Path) -> bool:
    if dest.exists():
        print(f"  [SKIP] {dest.name} 已存在")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  [DL]   下载 {url[:60]}...")
    result = subprocess.run(
        ["curl", "-sL", "--connect-timeout", "10", "--max-time", "120", "-o", str(dest), url],
        capture_output=True,
    )
    if result.returncode == 0:
        print(f"  [OK]   {dest.name} ({dest.stat().st_size // 1024} KB)")
        return True
    print(f"  [FAIL] 下载失败")
    return False


def extract(tool_name: str, archive: Path, dest_dir: Path):
    """Extract 7z and fix Windows symlink issues."""
    if dest_dir.exists():
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        print(f"  [EXTRACT] {archive.name}...")

        # Step 1: Extract ignoring symlink errors
        result = subprocess.run(
            [SEVEN_ZIP, "x", "-bd", f"-o{tmp_path}", str(archive)],
            capture_output=True, text=True,
        )
        if result.returncode not in (0, 2):
            print(f"  [FAIL] {result.stderr[:200]}")
            return False

        # Find content (7z may wrap in a subdirectory)
        items = list(tmp_path.iterdir())
        content = items[0] if len(items) == 1 and items[0].is_dir() else tmp_path

        # Step 2: Fix missing symlinks (create empty placeholder files)
        if tool_name == "winCodeSign":
            dylib_dir = content / "darwin" / "10.12" / "lib"
            for f in ["libcrypto.dylib", "libssl.dylib"]:
                fp = dylib_dir / f
                if not fp.exists():
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    fp.write_text("placeholder")
                    print(f"  [FIX]  已创建占位文件: {f}")

        shutil.copytree(content, dest_dir)

    print(f"  [OK]   {dest_dir}")

    # Step 3: Repack the 7z without symlinks (so app-builder can extract it)
    if tool_name == "winCodeSign":
        repacked = archive.with_suffix(".fixed.7z")
        if not repacked.exists():
            print(f"  [REPACK] 创建无符号链接的 7z...")
            subprocess.run(
                [SEVEN_ZIP, "a", "-mx=5", str(repacked), str(dest_dir)],
                capture_output=True,
            )
            # Replace the original 7z with the fixed one
            archive.unlink(missing_ok=True)
            repacked.rename(archive)
            print(f"  [OK]   已替换为修复版 7z ({archive.stat().st_size // 1024} KB)")


def ensure_cache(tool_name: str, info: dict):
    print(f"\n{'='*50}")
    print(f"  {tool_name}")
    print(f"{'='*50}")

    dest_dir = get_cache_dir(tool_name, info["url"])
    if dest_dir.exists() and any(dest_dir.iterdir()):
        print(f"  [CACHED] {dest_dir.name}")
        return True

    # Download the 7z archive
    archive_path = CACHE_DIR / tool_name / f"{tool_name}.7z"
    if not download(info["url"], archive_path):
        return False

    # Extract to cache
    extract(tool_name, archive_path, dest_dir)
    return True


def main():
    print("=" * 50)
    print("  Manchi 构建缓存初始化")
    print(f"  缓存目录: {CACHE_DIR}")
    print("=" * 50)
    print("  首次运行需要联网下载（约 8 MB）")
    print("  后续构建完全离线进行")
    print("=" * 50)

    all_ok = True
    for name, info in TOOLS.items():
        tool_name = name
        if not ensure_cache(name, info):
            print(f"  [WARN] {name} 缓存失败")
            all_ok = False

    if all_ok:
        print(f"\n{'='*50}")
        print(f"  缓存就绪！共 {sum(1 for _ in CACHE_DIR.rglob('*') if _.is_file())} 个文件")
        print(f"  位置: {CACHE_DIR}")
        print(f"  现在可以用 build.bat 或 build.py 构建了")
        print(f"{'='*50}")
    else:
        print(f"\n部分缓存失败，构建时可能需要联网")


if __name__ == "__main__":
    main()
