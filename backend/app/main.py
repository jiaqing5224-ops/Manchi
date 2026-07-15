"""
Manchi Backend — FastAPI application entry point.

Run with: uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_db()
    yield


app = FastAPI(
    title="Manchi API",
    description="Manchi Desktop AI Agent Backend",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow Electron frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Health ----
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "instance_token": os.environ.get("MANCHI_BACKEND_INSTANCE_TOKEN", ""),
    }


# ---- Routers ----
from app.routers import chat, mail, tasks, rules, settings, meeting, task_groups  # noqa: E402

app.include_router(chat.router)
app.include_router(mail.router)
app.include_router(tasks.router)
app.include_router(rules.router)
app.include_router(settings.router)
app.include_router(meeting.router)
app.include_router(task_groups.router)
