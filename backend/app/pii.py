from __future__ import annotations

import re


_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(r"\b(\+?\d{1,3}[\s-]?)?(\(?\d{3}\)?[\s-]?)\d{3}[\s-]?\d{4}\b")
_CREDIT_CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


def redact_pii(text: str) -> str:
    text = _EMAIL.sub("[REDACTED_EMAIL]", text)
    text = _PHONE.sub("[REDACTED_PHONE]", text)
    text = _CREDIT_CARD.sub("[REDACTED_CARD]", text)
    return text


def preview(text: str | None, limit: int = 280) -> str | None:
    if text is None:
        return None
    t = redact_pii(text)
    if len(t) <= limit:
        return t
    return t[:limit] + "…"

