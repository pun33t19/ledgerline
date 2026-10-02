"""Just enough Server-Sent Events (SSE) handling to inspect streamed MCP responses.

Streamable HTTP servers may answer a POST with ``text/event-stream``: a series
of events separated by blank lines, each carrying a JSON-RPC message in its
``data:`` line(s)::

    event: message
    data: {"jsonrpc":"2.0","id":3,"result":{...}}

The proxy splits the stream into events, reads each event's message, and
forwards the event's original bytes unless an interceptor replaces it.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

from ledgerline.jsonrpc import MAX_MESSAGE_BYTES

# An event ends at the first blank line; SSE allows \n, \r\n or \r line endings.
_EVENT_END = re.compile(rb"\r\n\r\n|\n\n|\r\r")


class EventTooLarge(ValueError):
    pass


async def split_events(chunks: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    """Re-chunk a byte stream into whole events (each including its terminating blank line)."""
    buffer = b""
    async for chunk in chunks:
        buffer += chunk
        while match := _EVENT_END.search(buffer):
            yield buffer[: match.end()]
            buffer = buffer[match.end() :]
        if len(buffer) > MAX_MESSAGE_BYTES:
            raise EventTooLarge(f"SSE event larger than {MAX_MESSAGE_BYTES} bytes")
    if buffer:
        yield buffer


def event_data(event: bytes) -> bytes | None:
    """The event's ``data`` field (multiple data lines are joined with newlines), or None."""
    lines = [line for line in event.splitlines() if line.startswith(b"data:")]
    if not lines:
        return None
    return b"\n".join(line[5:].removeprefix(b" ") for line in lines)


def with_data(event: bytes, data: bytes) -> bytes:
    """The same event (keeping ``event:``/``id:`` lines) with its data replaced."""
    kept = [line for line in event.splitlines() if line and not line.startswith(b"data:")]
    return b"\n".join([*kept, b"data: " + data]) + b"\n\n"
