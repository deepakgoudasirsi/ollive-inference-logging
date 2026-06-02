from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Literal, Optional

from .config import settings


Role = Literal["system", "user", "assistant"]


@dataclass
class ChatMessage:
    role: Role
    content: str


@dataclass
class StreamResult:
    full_text: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class BaseProvider:
    provider_name: str

    async def astream(self, *, model: str, messages: list[ChatMessage]) -> AsyncIterator[str]:
        raise NotImplementedError

    async def arun(self, *, model: str, messages: list[ChatMessage]) -> StreamResult:
        chunks: list[str] = []
        async for c in self.astream(model=model, messages=messages):
            chunks.append(c)
        return StreamResult(full_text="".join(chunks))


class MockProvider(BaseProvider):
    provider_name = "mock"

    async def astream(self, *, model: str, messages: list[ChatMessage]) -> AsyncIterator[str]:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        text = f"(mock:{model}) You said: {last_user}"
        for token in text.split(" "):
            await asyncio.sleep(0.03)
            yield (token + " ")


class OpenAIProvider(BaseProvider):
    provider_name = "openai"

    def __init__(self) -> None:
        from openai import AsyncOpenAI  # type: ignore

        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def astream(self, *, model: str, messages: list[ChatMessage]) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            stream=True,
        )
        async for event in stream:
            delta = (event.choices[0].delta.content or "") if event.choices else ""
            if delta:
                yield delta


class AnthropicProvider(BaseProvider):
    provider_name = "anthropic"

    def __init__(self) -> None:
        from anthropic import AsyncAnthropic  # type: ignore

        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def astream(self, *, model: str, messages: list[ChatMessage]) -> AsyncIterator[str]:
        system = next((m.content for m in messages if m.role == "system"), None)
        converted = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        stream = await self._client.messages.create(
            model=model,
            system=system,
            max_tokens=512,
            messages=converted,
            stream=True,
        )
        async for event in stream:
            if event.type == "content_block_delta" and event.delta.type == "text_delta":
                yield event.delta.text


def get_provider(name: str) -> BaseProvider:
    name = (name or "mock").lower()
    if name == "openai":
        return OpenAIProvider()
    if name == "anthropic":
        return AnthropicProvider()
    return MockProvider()

