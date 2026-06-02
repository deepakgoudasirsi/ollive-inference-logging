from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Iterator

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select, func

from .config import settings
from .db import engine, init_db
from .inference_logger import InferenceLogger, new_event, set_previews
from .llm_providers import ChatMessage, get_provider
from .models import Conversation, Message, InferenceLog, utcnow
from .pii import preview
from .schemas import (
    ConversationOut,
    CreateConversationIn,
    IngestInferenceIn,
    MessageOut,
    MetricsSummaryOut,
    SendMessageIn,
)


app = FastAPI(title="Ollive Lightweight Inference Logging")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@app.on_event("startup")
def _startup() -> None:
    init_db()


def _require_ingest_key(authorization: str | None) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing ingest auth")
    token = authorization.split(" ", 1)[1].strip()
    if token != settings.ingest_api_key:
        raise HTTPException(status_code=403, detail="Invalid ingest auth")


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/conversations", response_model=ConversationOut)
def create_conversation(payload: CreateConversationIn, db: Session = Depends(get_db)) -> Conversation:
    convo = Conversation(title=payload.title or "New conversation")
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return convo


@app.get("/api/conversations", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db)) -> list[Conversation]:
    return list(db.exec(select(Conversation).order_by(Conversation.updated_at.desc())))


@app.get("/api/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(conversation_id: str, db: Session = Depends(get_db)) -> list[Message]:
    convo = db.get(Conversation, conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return list(
        db.exec(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()))
    )


@app.post("/api/conversations/{conversation_id}/cancel", response_model=ConversationOut)
def cancel_conversation(conversation_id: str, db: Session = Depends(get_db)) -> Conversation:
    convo = db.get(Conversation, conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    convo.status = "cancelled"
    convo.updated_at = utcnow()
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return convo


@app.post("/api/conversations/{conversation_id}/chat/stream")
async def chat_stream(
    conversation_id: str,
    payload: SendMessageIn,
    request: Request,
    x_session_id: str | None = Header(default=None),
) -> StreamingResponse:
    db = Session(engine)
    convo = db.get(Conversation, conversation_id)
    if not convo:
        db.close()
        raise HTTPException(status_code=404, detail="Conversation not found")
    if convo.status != "active":
        db.close()
        raise HTTPException(status_code=409, detail="Conversation is cancelled")

    user_msg = Message(conversation_id=conversation_id, role="user", content=payload.content)
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    # Keep short context (tradeoff: cost/latency vs coherence)
    history = list(
        db.exec(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()))
    )
    history = history[-8:]
    messages = [ChatMessage(role=m.role, content=m.content) for m in history]

    provider = get_provider(settings.llm_provider)
    model = settings.llm_model

    event = new_event(provider=provider.provider_name, model=model, session_id=x_session_id)
    event.conversation_id = conversation_id
    event.request_message_id = user_msg.id
    set_previews(event, request_text=payload.content, response_text=None)

    logger = InferenceLogger()
    started = time.perf_counter()

    async def _gen():
        yield _sse({"type": "meta", "inference_id": event.id, "trace_id": event.trace_id})
        chunks: list[str] = []
        try:
            async for delta in provider.astream(model=model, messages=messages):
                if await request.is_disconnected():
                    event.status = "cancelled"
                    yield _sse({"type": "done", "status": "cancelled"})
                    return
                chunks.append(delta)
                yield _sse({"type": "delta", "text": delta})

            full = "".join(chunks).strip()
            assistant_msg = Message(conversation_id=conversation_id, role="assistant", content=full)
            db.add(assistant_msg)
            convo.updated_at = utcnow()
            db.add(convo)
            db.commit()
            db.refresh(assistant_msg)

            event.response_message_id = assistant_msg.id
            event.status = "success"
            event.finished_at = datetime.utcnow()
            event.latency_ms = int((time.perf_counter() - started) * 1000)
            set_previews(event, request_text=payload.content, response_text=full)

            logger.send_background(event)
            yield _sse({"type": "done", "status": "success", "message_id": assistant_msg.id})
        except Exception as e:
            event.status = "error"
            event.error_type = type(e).__name__
            event.error_message = str(e)[:500]
            event.finished_at = datetime.utcnow()
            event.latency_ms = int((time.perf_counter() - started) * 1000)
            logger.send_background(event)
            yield _sse({"type": "done", "status": "error", "error": event.error_message})
        finally:
            db.close()

    return StreamingResponse(_gen(), media_type="text/event-stream")


@app.post("/api/ingest/inference")
def ingest_inference(
    payload: IngestInferenceIn,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    _require_ingest_key(authorization)

    log = InferenceLog(
        id=payload.id,
        provider=payload.provider,
        model=payload.model,
        started_at=payload.started_at,
        finished_at=payload.finished_at,
        latency_ms=payload.latency_ms,
        status=payload.status,
        error_type=payload.error_type,
        error_message=(payload.error_message[:500] if payload.error_message else None),
        prompt_tokens=payload.prompt_tokens,
        completion_tokens=payload.completion_tokens,
        total_tokens=payload.total_tokens,
        session_id=payload.session_id,
        conversation_id=payload.conversation_id,
        request_message_id=payload.request_message_id,
        response_message_id=payload.response_message_id,
        trace_id=payload.trace_id,
        request_preview=preview(payload.request_preview),
        response_preview=preview(payload.response_preview),
    )
    db.add(log)
    db.commit()
    return {"ok": True, "id": log.id}


@app.get("/api/metrics/summary", response_model=MetricsSummaryOut)
def metrics_summary(db: Session = Depends(get_db)) -> MetricsSummaryOut:
    total = db.exec(select(func.count(InferenceLog.id))).one()
    success = db.exec(select(func.count(InferenceLog.id)).where(InferenceLog.status == "success")).one()
    error = db.exec(select(func.count(InferenceLog.id)).where(InferenceLog.status == "error")).one()
    cancelled = db.exec(select(func.count(InferenceLog.id)).where(InferenceLog.status == "cancelled")).one()
    avg_latency = db.exec(
        select(func.avg(InferenceLog.latency_ms)).where(InferenceLog.latency_ms.is_not(None))
    ).one()
    return MetricsSummaryOut(
        total_inferences=int(total),
        success=int(success),
        error=int(error),
        cancelled=int(cancelled),
        avg_latency_ms=float(avg_latency) if avg_latency is not None else None,
    )


@app.get("/api/metrics/recent")
def metrics_recent(db: Session = Depends(get_db)) -> list[dict]:
    rows = list(db.exec(select(InferenceLog).order_by(InferenceLog.started_at.desc()).limit(50)))
    return [
        {
            "id": r.id,
            "started_at": r.started_at,
            "latency_ms": r.latency_ms,
            "status": r.status,
            "provider": r.provider,
            "model": r.model,
            "conversation_id": r.conversation_id,
            "request_preview": r.request_preview,
            "response_preview": r.response_preview,
            "error_type": r.error_type,
        }
        for r in rows
    ]

