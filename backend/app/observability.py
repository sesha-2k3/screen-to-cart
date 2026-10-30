"""Langfuse setup: one process-wide client, per-request handlers, named traces."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from langfuse import Langfuse, get_client, observe, propagate_attributes
from langfuse.langchain import CallbackHandler
from pydantic import SecretStr

from app.config import Settings

# Phase 0 constant; becomes a setting when providers change (build plan section 7).
PROVIDER_TAG = "groq-free"

__all__ = [
    "PROVIDER_TAG",
    "init_langfuse",
    "new_callback_handler",
    "observe",
    "shutdown_langfuse",
    "trace_attributes",
]

logger = logging.getLogger(__name__)


def _reveal(secret: SecretStr | None) -> str | None:
    return secret.get_secret_value() if secret else None


def init_langfuse(settings: Settings) -> Langfuse:
    """Create the process-wide client from Settings. Tracing is disabled when keys are missing."""
    enabled = bool(settings.langfuse_public_key and settings.langfuse_secret_key)
    return Langfuse(
        public_key=_reveal(settings.langfuse_public_key),
        secret_key=_reveal(settings.langfuse_secret_key),
        base_url=settings.langfuse_base_url,
        tracing_enabled=enabled,
    )


def shutdown_langfuse() -> None:
    # Runs at app shutdown, outside any request, so a failed flush is logged, not raised.
    try:
        get_client().shutdown()
    except Exception:
        logger.exception("Langfuse shutdown failed")


def new_callback_handler() -> CallbackHandler:
    """Return a new handler on every call. Never cache or share across requests."""
    return CallbackHandler()


@contextmanager
def trace_attributes(
    trace_name: str,
    session_id: str | None = None,
    tags: list[str] | None = None,
) -> Iterator[None]:
    """Name the current trace and tag it, with the provider tag always first."""
    all_tags = [PROVIDER_TAG, *(t for t in (tags or []) if t != PROVIDER_TAG)]
    with propagate_attributes(
        trace_name=trace_name, session_id=session_id, tags=all_tags
    ):
        yield
