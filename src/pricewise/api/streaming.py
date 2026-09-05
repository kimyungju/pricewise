import json
from collections.abc import Mapping
from pydantic import JsonValue


def format_sse_event(event: str, data: Mapping[str, JsonValue]) -> str:
    """Format a Server-Sent Event string.

    Args:
        event: Event type name (e.g. "token", "approval_required", "done")
        data: Event payload dict, will be JSON-serialized

    Returns:
        Formatted SSE string: "event: <type>\\ndata: <json>\\n\\n"
    """
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
