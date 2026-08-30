import json
from collections.abc import AsyncIterator
from typing import Any


def format_sse_event(
    event: str,
    data: dict[str, Any] | list[Any],
    *,
    event_id: str | None = None,
) -> str:
    """Format a single Server-Sent Events frame."""
    payload = json.dumps(data, default=str)
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {payload}")
    lines.append("")
    return "\n".join(lines) + "\n"


async def sse_event_stream(
    chunks: AsyncIterator[str],
) -> AsyncIterator[str]:
    async for chunk in chunks:
        yield chunk
