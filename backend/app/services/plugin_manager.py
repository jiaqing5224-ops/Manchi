"""Plugin manager — discover, load, run, export and import Manchi components.

A component is a folder `<components_dir>/<name>/` containing `manifest.json`
(metadata) and `component.py` (logic with `run(params, context)`). System
components are registered separately; this manager handles the on-disk
"custom" components plus the shared dependency-merge / install logic.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Optional

DEFAULT_COMPONENTS_DIR = Path(os.path.expanduser("~/Documents/Manchi/components"))


class PluginManager:
    def __init__(self, components_dir: Optional[str | Path] = None) -> None:
        self.components_dir = Path(
            components_dir
            or os.environ.get("MANCHI_COMPONENTS", DEFAULT_COMPONENTS_DIR)
        ).expanduser().resolve()
        self._module_cache: dict[str, tuple[float, Any]] = {}

    # ---- discovery / metadata ----

    def discover_components(self) -> dict[str, dict]:
        """Scan <components_dir>/<name>/manifest.json -> {name: manifest}."""
        result: dict[str, dict] = {}
        if not self.components_dir.is_dir():
            return result
        for folder in sorted(self.components_dir.iterdir()):
            mj = folder / "manifest.json"
            if folder.is_dir() and mj.exists():
                try:
                    meta = json.loads(mj.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if meta.get("name") == folder.name:
                    result[folder.name] = meta
        return result

    def get_component_meta(self, name: str) -> Optional[dict]:
        return self.discover_components().get(name)

    def list_components(self, category: Optional[str] = None) -> list[dict]:
        metas = list(self.discover_components().values())
        if category:
            metas = [m for m in metas if m.get("source") == category]
        return metas

    # ---- loading / execution ----

    def _load_module(self, name: str):
        py_path = self.components_dir / name / "component.py"
        if not py_path.exists():
            raise FileNotFoundError(f"组件 {name} 缺少 component.py")
        mtime = py_path.stat().st_mtime
        cached = self._module_cache.get(name)
        if cached and cached[0] == mtime:
            return cached[1]
        spec = importlib.util.spec_from_file_location(f"_manchi_{name}", str(py_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        self._module_cache[name] = (mtime, mod)
        return mod

    def run_component(self, name: str, params: dict, context: dict) -> Any:
        mod = self._load_module(name)
        if not hasattr(mod, "run"):
            raise ValueError(f"组件 {name} 缺少 run() 函数")
        return mod.run(params or {}, context)

    # ---- export / import ----

    def export_component(self, name: str) -> bytes:
        src = self.components_dir / name
        if not src.is_dir():
            raise FileNotFoundError(name)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(src.rglob("*")):
                if f.is_file():
                    zf.write(f, arcname=f.relative_to(src))
        return buf.getvalue()

    def import_component(self, zip_bytes: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            manifest_entry = next((n for n in names if n.endswith("manifest.json")), None)
            if manifest_entry is None:
                raise ValueError("zip 内缺少 manifest.json")
            top = manifest_entry.split("/")[0] if "/" in manifest_entry else "."
            meta = json.loads(zf.read(manifest_entry))
            name = meta["name"]
            dest = self.components_dir / name
            dest.mkdir(parents=True, exist_ok=True)
            for n in names:
                if n.endswith("/"):
                    continue
                data = zf.read(n)
                rel = n[len(top) + 1:] if (top != "." and n.startswith(top + "/")) else n
                if not rel:
                    continue
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        self._merge_requires(meta.get("requires", []), name)
        self._module_cache.pop(name, None)
        return name

    def import_component_files(self, file_map: dict[str, bytes]) -> str:
        """Import a component from a folder: {relative_path: file_bytes}.

        Used when the UI selects a component folder (webkitdirectory) so each
        file carries its relative path (e.g. "excel_to_markdown/manifest.json").
        The top-level folder name from the path is stripped and the component is
        written under <components_dir>/<manifest.name>/.
        """
        manifest_rel = next((r for r in file_map if r.endswith("manifest.json")), None)
        if manifest_rel is None:
            raise ValueError("组件文件夹内缺少 manifest.json")
        meta = json.loads(file_map[manifest_rel])
        name = meta["name"]
        top = manifest_rel.split("/", 1)[0] if "/" in manifest_rel else ""
        dest = self.components_dir / name
        dest.mkdir(parents=True, exist_ok=True)
        for rel, data in file_map.items():
            parts = rel.split("/")
            if top and parts and parts[0] == top:
                parts = parts[1:]
            rel_inner = "/".join(parts)
            if not rel_inner:
                continue
            target = dest / rel_inner
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        self._merge_requires(meta.get("requires", []), name)
        self._module_cache.pop(name, None)
        return name

    def _merge_requires(self, requires: list[str], name: str) -> None:
        req_file = self.components_dir / "requirements.txt"
        existing = (
            req_file.read_text(encoding="utf-8").splitlines() if req_file.exists() else []
        )
        base = [
            l.split("#")[0].strip()
            for l in existing
            if l.strip() and not l.strip().startswith("#")
        ]
        changed = False
        for pkg in requires or []:
            if pkg and pkg not in base:
                existing.append(pkg)
                existing.append(f"# 来自组件: {name}")
                base.append(pkg)
                changed = True
        if changed:
            req_file.write_text("\n".join(existing) + "\n", encoding="utf-8")

    def sync_all_requires(self) -> None:
        """Merge every discovered component's ``requires`` into the shared
        requirements.txt. Ensures components copied directly into the folder
        (not via import) still get their dependencies tracked + installed."""
        for name, meta in self.discover_components().items():
            self._merge_requires(meta.get("requires", []) or [], name)

    @staticmethod
    def _pkg_top(pkg: str) -> str:
        return (
            pkg.split("==")[0].split(">=")[0].split("<")[0].strip().replace("-", "_")
        )

    # ---- dependency installation ----

    def _runtime_python(self) -> str:
        """Resolve the Python interpreter that owns the app's dependencies.

        Priority:
          1. MANCHI_RUNTIME env var (explicit override)
          2. the dedicated Manchi venv at <Manchi>/venv (sibling of components/)
          3. fallback to the interpreter currently running the backend
        Dependencies are always installed into this interpreter so they
        survive regardless of how the backend process was launched.
        """
        env = os.environ.get("MANCHI_RUNTIME")
        if env:
            return env
        venv = self.components_dir.parent / "venv"
        cand = (venv / "Scripts" / "python.exe") if os.name == "nt" else (venv / "bin" / "python")
        if cand.exists():
            return str(cand)
        return sys.executable

    def _ensure_pkg(self, python: str, pkg: str, top: str) -> None:
        """Install `pkg` into `python` only if `top` is not already importable."""
        check = subprocess.run(
            [python, "-c", f"import importlib.util,sys;sys.exit(0 if importlib.util.find_spec({top!r}) else 1)"],
            capture_output=True,
        )
        if check.returncode != 0:
            subprocess.run([python, "-m", "pip", "install", pkg], check=False)

    def _collect_post_install(self) -> list[str]:
        """Gather post-install shell commands from all components + built-ins.

        A component may declare ``post_install: ["playwright install chromium"]``
        in its manifest. We also auto-append the Chromium download whenever
        ``playwright`` appears in any requirement.
        """
        cmds: list[str] = []
        have_playwright = False
        for name, meta in self.discover_components().items():
            for c in meta.get("post_install", []) or []:
                if c and c not in cmds:
                    cmds.append(c)
            for r in meta.get("requires", []) or []:
                if self._pkg_top(r) == "playwright":
                    have_playwright = True
        if have_playwright and "playwright install chromium" not in cmds:
            cmds.append("playwright install chromium")
        return cmds

    def install_dependencies(self) -> dict:
        """Install all tracked component deps, then run post-install hooks.

        Returns a summary so the UI can report what changed.
        """
        self.sync_all_requires()
        req_file = self.components_dir / "requirements.txt"
        if not req_file.exists():
            return {"ok": True, "installed": [], "post_install": []}
        python = self._runtime_python()
        installed: list[str] = []
        for line in req_file.read_text(encoding="utf-8").splitlines():
            pkg = line.split("#")[0].strip()
            if not pkg:
                continue
            top = self._pkg_top(pkg)
            try:
                self._ensure_pkg(python, pkg, top)
                installed.append(pkg)
            except Exception:
                pass
        post_install: list[str] = []
        for cmd in self._collect_post_install():
            try:
                subprocess.run(
                    [python, "-m", *cmd.split()],
                    capture_output=True,
                )
                post_install.append(cmd)
            except Exception:
                pass
        return {"ok": True, "installed": installed, "post_install": post_install}
