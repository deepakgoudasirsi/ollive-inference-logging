from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field


class ConversationOut(BaseModel):
    id: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime


class CreateConversationIn(BaseModel):
    title: str | None = None


class SendMessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class IngestInferenceIn(BaseModel):
    id: str
    provider: str
    model: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    latency_ms: Optional[int] = None
    status: str
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


class MetricsSummaryOut(BaseModel):
    total_inferences: int
    success: int
    error: int
    cancelled: int
    avg_latency_ms: Optional[float] = None

