"""Observability — LangSmith traces and PostHog events.

Both are soft dependencies: if the user hasn't set `LANGSMITH_TRACING=true`
and `LANGSMITH_API_KEY`, `@traceable` is a no-op decorator. If
`POSTHOG_API_KEY` is unset, `emit()` and `flush()` are no-ops.
"""

from __future__ import annotations

import os
from typing import Any

try:
    from langsmith import traceable as _traceable
except ImportError:  # pragma: no cover

    def _traceable(fn):
        return fn


# Public alias so callers don't have to care whether LangSmith is installed.
traceable = _traceable


_posthog_client: Any = None

try:
    import posthog as _posthog_mod

    if os.environ.get("POSTHOG_API_KEY"):
        _posthog_mod.api_key = os.environ["POSTHOG_API_KEY"]
        _posthog_mod.host = os.environ.get(
            "POSTHOG_HOST", "https://us.i.posthog.com"
        )
        _posthog_client = _posthog_mod
except ImportError:  # pragma: no cover
    pass


def emit(session_id: str, event: str, properties: dict) -> None:
    """Fire-and-forget a PostHog event. Silent no-op if PostHog isn't set up."""
    if _posthog_client is None:
        return
    try:
        _posthog_client.capture(
            distinct_id=session_id, event=event, properties=properties
        )
    except Exception:
        # We don't want observability to break the agent.
        pass


def flush() -> None:
    if _posthog_client is None:
        return
    try:
        _posthog_client.flush()
    except Exception:
        pass


def posthog_enabled() -> bool:
    return _posthog_client is not None


def langsmith_enabled() -> bool:
    return os.environ.get("LANGSMITH_TRACING", "").lower() in {"true", "1", "yes"}
