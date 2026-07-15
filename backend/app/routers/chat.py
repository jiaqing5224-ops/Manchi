"""
Chat router — SSE streaming chat with the AI assistant.
"""

import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.conversation import Conversation
from app.schemas.chat import ChatRequest
from app.services.llm.client import chat_stream_with_tools

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/stream")
async def stream_chat(req: ChatRequest, db: Session = Depends(get_db)):
    """Stream a chat response via SSE."""

    # Persist user message
    db.add(Conversation(session_id=req.session_id, role="user", content=req.message))
    db.commit()

    async def event_generator():
        full_response = ""
        try:
            for chunk in chat_stream_with_tools(req.history, req.message, db):
                yield f"data: {chunk}\n\n"
                # Track assistant text for persistence (tool events are skipped)
                try:
                    evt = json.loads(chunk)
                    if "text" in evt:
                        full_response += evt["text"]
                except json.JSONDecodeError:
                    pass

            # Persist assistant response
            db.add(
                Conversation(
                    session_id=req.session_id,
                    role="assistant",
                    content=full_response,
                )
            )
            db.commit()

        except Exception as e:
            yield f"data: {json.dumps({'text': f'Error: {str(e)}'})}\n\n"

        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history/{session_id}")
def get_history(session_id: str, db: Session = Depends(get_db)):
    """Retrieve conversation history for a session."""
    messages = (
        db.query(Conversation)
        .filter(Conversation.session_id == session_id)
        .order_by(Conversation.created_at)
        .all()
    )
    return [
        {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
        for m in messages
    ]


@router.delete("/history/{session_id}")
def clear_history(session_id: str, db: Session = Depends(get_db)):
    """Clear conversation history for a session."""
    db.query(Conversation).filter(Conversation.session_id == session_id).delete()
    db.commit()
    return {"ok": True}
