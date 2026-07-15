"""
PyInstaller entry point for Manchi backend.
Run via: python -m uvicorn app.main:app
This file serves as the boot script for PyInstaller.
"""
import sys
import os

# Ensure app package is discoverable when bundled
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )
