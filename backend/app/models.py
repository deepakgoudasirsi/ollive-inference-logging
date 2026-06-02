from datetime import datetime
from typing import Optional, List
from uuid import uuid4

from sqlmodel import SQLModel, Field, Relationship


def utcnow() -> datetime:
    return datetime.utcnow()


class Conversation(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, index=True)
    title: str = Field(default="New conversation", index=True)
    status: str = Field(default="active", index=True)  # active | cancelled
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)

    messages: List["Message"] = Relationship(back_populates="conversation")


class Message(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, index=True)
    conversation_id: str = Field(foreign_key="conversation.id", index=True)
    role: str = Field(index=True)  # user | assistant | system
    content: str
    created_at: datetime = Field(default_factory=utcnow, index=True)

    conversation: Optional[Conversation] = Relationship(back_populates="messages")


class InferenceLog(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, index=True)

    conversation_id: Optional[str] = Field(default=None, foreign_key="conversation.id", index=True)
    request_message_id: Optional[str] = Field(default=None, foreign_key="message.id", index=True)
    response_message_id: Optional[str] = Field(default=None, foreign_key="message.id", index=True)

    provider: str = Field(index=True)
    model: str = Field(index=True)

    started_at: datetime = Field(index=True)
    finished_at: Optional[datetime] = Field(default=None, index=True)
    latency_ms: Optional[int] = Field(default=None, index=True)

    status: str = Field(index=True)  # success | error | cancelled
    error_type: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)

    prompt_tokens: Optional[int] = Field(default=None)
    completion_tokens: Optional[int] = Field(default=None)
    total_tokens: Optional[int] = Field(default=None)

    request_preview: Optional[str] = Field(default=None)
    response_preview: Optional[str] = Field(default=None)

    session_id: Optional[str] = Field(default=None, index=True)
    trace_id: Optional[str] = Field(default=None, index=True)

