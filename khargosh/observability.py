"""Observability with Langfuse (D24, D25, D26).

This is the ONLY file that imports Langfuse. The other files use the
functions below. If we change the platform later, we change only this file.

How it works:
- `@observe(...)` above a function records each call as a span.
  Langfuse nests the spans automatically: a model call inside an agent turn
  becomes a child of that turn.
- `init()` must run before the first traced call, because Langfuse keeps
  one client for the whole program (a singleton).
- `_mask()` removes secrets before any data leaves the computer (D26).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from langfuse import Langfuse, get_client, observe, propagate_attributes

__all__ = ["init", "observe", "session", "record_generation", "shutdown"]

# Text that looks like a secret. Each match becomes "[REDACTED]".
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),  # Anthropic, OpenAI, OpenRouter, Langfuse secret keys
    re.compile(r"pk-lf-[A-Za-z0-9_\-]{8,}"),  # Langfuse public key
    re.compile(r"gsk_[A-Za-z0-9]{16,}"),  # Groq
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),  # Google
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key ID
]
# Lines like "SOME_API_KEY=value" or "password: value" (for example, the output of `cat .env`).
_ASSIGNMENT = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD)[A-Z0-9_]*\s*[=:]\s*)([^\s\"']+)"
)
_REDACTED = "[REDACTED]"

# The real values of secret environment variables, filled in by init().
_known_secrets: list[str] = []


def init(enabled: bool) -> bool:
    """Create the Langfuse client. Return True if tracing is active."""
    global _known_secrets
    _known_secrets = sorted(
        {
            value
            for name, value in os.environ.items()
            if len(value) >= 12 and any(word in name.upper() for word in ("KEY", "SECRET", "TOKEN", "PASSWORD"))
        },
        key=len,
        reverse=True,  # replace longer values first
    )

    has_keys = bool(os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"))
    active = enabled and has_keys
    if not active:
        # Without keys, Langfuse logs an "Authentication error" warning. That is expected here.
        os.environ["LANGFUSE_TRACING_ENABLED"] = "false"
        logging.getLogger("langfuse").setLevel(logging.ERROR)

    Langfuse(mask=_mask, tracing_enabled=active)
    return active


def session(session_id: str):
    """Group all traces of one Khargosh session in Langfuse. Use it as `with session(...):`."""
    return propagate_attributes(session_id=session_id, trace_name="khargosh-turn")


def record_generation(
    *,
    model: str,
    input: Any,
    output: Any,
    usage: dict[str, int],
    cost: dict[str, float] | None,
) -> None:
    """Add model, tokens, and cost to the current generation span."""
    get_client().update_current_generation(
        model=model,
        input=input,
        output=output,
        usage_details=usage,
        cost_details=cost,
    )


def shutdown() -> None:
    """Send the remaining traces before the program stops."""
    get_client().shutdown()


def _mask(*, data: Any, **kwargs: Any) -> Any:
    """Langfuse calls this for each input, output, and metadata value before it sends it."""
    if isinstance(data, str):
        return _mask_text(data)
    if isinstance(data, dict):
        return {key: _mask(data=value) for key, value in data.items()}
    if isinstance(data, (list, tuple)):
        return [_mask(data=item) for item in data]
    if hasattr(data, "model_dump"):  # Pydantic objects, for example a LiteLLM message
        return _mask(data=data.model_dump())
    return data


def _mask_text(text: str) -> str:
    for secret in _known_secrets:
        text = text.replace(secret, _REDACTED)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(_REDACTED, text)
    return _ASSIGNMENT.sub(lambda match: match.group(1) + _REDACTED, text)
