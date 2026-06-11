"""Tracing / observability integration.

Langfuse is wired in as a LangChain callback handler so every agent run
produces a full trace: LLM calls, tool calls, latencies, and token usage.

Tracing is strictly opt-in: if the LANGFUSE_* keys are absent (local dev,
CI unit tests) this module degrades to a no-op so the agent never takes a
hard dependency on the tracing backend.

Required environment variables to enable tracing:
    LANGFUSE_PUBLIC_KEY
    LANGFUSE_SECRET_KEY
    LANGFUSE_HOST (optional, defaults to https://cloud.langfuse.com)
"""

import logging
import os

logger = logging.getLogger(__name__)

_handler = None
_initialized = False


def tracing_enabled() -> bool:
    """True when Langfuse credentials are configured."""
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def get_callbacks() -> list:
    """Return LangChain callback handlers for the current environment.

    Returns a singleton Langfuse ``CallbackHandler`` when credentials are
    set, otherwise an empty list. Safe to call on every request.
    """
    global _handler, _initialized

    if not tracing_enabled():
        return []

    if not _initialized:
        _initialized = True
        try:
            from langfuse.langchain import CallbackHandler

            _handler = CallbackHandler()
            logger.info("Langfuse tracing enabled")
        except Exception as exc:  # pragma: no cover - import/config errors
            logger.warning("Langfuse tracing disabled: %s", exc)
            _handler = None

    return [_handler] if _handler else []


def agent_config(thread_id: str, **metadata) -> dict:
    """Build a LangGraph runnable config with tracing callbacks attached.

    Extra keyword arguments become trace metadata (e.g. session ids,
    eval task ids) so traces can be filtered in the Langfuse UI.
    """
    config = {
        "configurable": {"thread_id": thread_id},
        "callbacks": get_callbacks(),
    }
    if metadata:
        config["metadata"] = metadata
    return config
