"""Component management API — list / import / export / delete / install deps.

Backed by PluginManager (on-disk "custom" components) and the unified
COMPONENT_REGISTRY (system + custom) from the orchestrator actions module.
"""
from __future__ import annotations

import io
import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.services.plugin_manager import PluginManager
from app.services.orchestrator.actions import COMPONENT_REGISTRY, refresh_components

router = APIRouter(prefix="/api/components", tags=["components"])

_pm = PluginManager()


@router.get("")
def list_components() -> list[dict]:
    """List all components (system + custom) with their manifest metadata.

    The on-disk manifest JSON does not carry `source` (that is decided by the
    registry: system actions vs discovered custom components). Inject it here so
    the frontend can reliably tell custom components apart.
    """
    return [
        {**entry["manifest"], "source": entry["source"]}
        for entry in COMPONENT_REGISTRY.values()
    ]


@router.get("/{name}")
def get_component(name: str) -> dict:
    entry = COMPONENT_REGISTRY.get(name)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"组件不存在: {name}")
    return {**entry["manifest"], "source": entry["source"]}


@router.post("/import")
async def import_component(files: list[UploadFile] = File(...)) -> dict:
    """Import a component.

    Accepts either:
      - a single .zip archive (exported via /export), or
      - a folder selected via the UI's webkitdirectory picker (one UploadFile
        per file, each UploadFile.filename carrying the relative path).
    """
    try:
        if len(files) == 1 and (files[0].filename or "").lower().endswith(".zip"):
            data = await files[0].read()
            name = _pm.import_component(data)
        else:
            file_map = {f.filename or "": await f.read() for f in files}
            name = _pm.import_component_files(file_map)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    refresh_components()
    meta = _pm.get_component_meta(name)
    return {"name": name, "manifest": meta}


@router.get("/{name}/export")
def export_component(name: str) -> Response:
    if name not in _pm.discover_components():
        raise HTTPException(status_code=404, detail=f"组件不存在: {name}")
    try:
        blob = _pm.export_component(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"组件不存在: {name}")
    return Response(
        blob,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={name}.zip"},
    )


@router.delete("/{name}")
def delete_component(name: str) -> dict:
    """Delete a custom component (cannot delete system components)."""
    meta = _pm.get_component_meta(name)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"组件不存在: {name}")
    if meta.get("source") != "custom":
        raise HTTPException(status_code=400, detail="系统组件不可删除")
    folder = _pm.components_dir / name
    if folder.exists():
        shutil.rmtree(folder)
    refresh_components()
    return {"deleted": name}


@router.post("/install-deps")
def install_deps() -> dict:
    """Install any missing dependencies + run post-install hooks (e.g. the
    Chromium browser binary download for playwright)."""
    return _pm.install_dependencies()
