from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

import httpx


def _redact_preview(text: str | None, limit: int = 280) -> str | None:
    # SDK-side previewing to reduce payload size + avoid shipping full text.
    if text is None:
        return None
    t = text
    if len(t) <= limit:
        return t
    return t[:limit] + "…"


@dataclass
class InferenceEvent:
    id: str
    provider: str
    model: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    latency_ms: Optional[int] = None
    status: str = "success"
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    request_message_id: Optional[str] = None
    response_message_id: Optional[str] = None
    trace_id: Optional[str] = None
    request_preview: Optional[str] = None
    response_preview: Optional[str] = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider,
            "model": self.model,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "latency_ms": self.latency_ms,
            "status": self.status,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
            "request_message_id": self.request_message_id,
            "response_message_id": self.response_message_id,
            "trace_id": self.trace_id,
            "request_preview": self.request_preview,
            "response_preview": self.response_preview,
        }


class InferenceLogger:
    def __init__(self, *, ingestion_url: str, api_key: str, timeout_s: float = 3.0) -> None:
        self.ingestion_url = ingestion_url
        self.api_key = api_key
        self.timeout_s = timeout_s

    async def send(self, event: InferenceEvent) -> None:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            await client.post(self.ingestion_url, json=event.to_payload(), headers=headers)

    def send_background(self, event: InferenceEvent, retries: int = 3) -> None:
        async def _runner() -> None:
            for attempt in range(retries):
                try:
                    await self.send(event)
                    return
                except Exception:
                    await asyncio.sleep(0.2 * (2**attempt))

        asyncio.create_task(_runner())


def new_event(*, provider: str, model: str, session_id: str | None = None) -> InferenceEvent:
    return InferenceEvent(
        id=str(uuid4()),
        provider=provider,
        model=model,
        started_at=datetime.utcnow(),
        session_id=session_id,
        trace_id=str(uuid4()),
    )


def set_previews(event: InferenceEvent, *, request_text: str | None, response_text: str | None) -> None:
    event.request_preview = _redact_preview(request_text)
    event.response_preview = _redact_preview(response_text)

