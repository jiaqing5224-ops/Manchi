"""Meeting router — generate weekly meeting Excel report."""

import os
import sys

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.meeting.meeting_service import generate_meeting_excel, get_exports_dir

router = APIRouter(prefix="/api/meeting", tags=["meeting"])


@router.post("/report")
def meeting_report(db: Session = Depends(get_db)):
    """Scan this week's meeting emails and export an Excel to the exports dir."""
    try:
        return generate_meeting_excel(db)
    except Exception as e:
        raise HTTPException(500, f"Meeting report failed: {e}")


@router.get("/exports-dir")
def exports_dir() -> dict:
    """Return the path of the dedicated exports directory."""
    return {"path": get_exports_dir()}


@router.post("/open-exports")
def open_exports() -> dict:
    """Open the exports directory in the OS file explorer."""
    path = get_exports_dir()
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            import subprocess
            subprocess.run(["open", path], check=False)
        else:
            import subprocess
            subprocess.run(["xdg-open", path], check=False)
        return {"ok": True, "path": path}
    except Exception as e:
        raise HTTPException(500, f"Open exports dir failed: {e}")
