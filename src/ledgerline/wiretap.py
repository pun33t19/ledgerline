"""Record the JSON-RPC messages flowing over an MCP client transport as JSON Lines.

Wrap any transport (stdio or Streamable HTTP) in :class:`Wiretap` and every
message the client sends or receives is written as one line::

    {"dir": "sent" | "received", "msg": <JSON-RPC message>}

The output is used to capture golden fixtures (``testdata/mcp/*.jsonl``) that
the Phase 2 proxy must relay unchanged.
"""

from __future__ import annotations

import json
from types import TracebackType
from typing import Any, Literal, Self, TextIO

from mcp.client._transport import ReadStream, Transport, TransportStreams, WriteStream
from mcp.shared.message import SessionMessage

Direction = Literal["sent", "received"]


def encode(message: SessionMessage) -> dict[str, Any]:
    """The message as the SDK puts it on the wire (same options as its stdio transport)."""
    data: dict[str, Any] = message.message.model_dump(by_alias=True, mode="json", exclude_unset=True)
    return data


class Wiretap:
    """A transport wrapper that copies every message to ``out`` without changing it."""

    def __init__(self, inner: Transport, out: TextIO) -> None:
        self._inner = inner
        self._out = out

    def record(self, direction: Direction, message: SessionMessage) -> None:
        line = json.dumps(
            {"dir": direction, "msg": encode(message)}, ensure_ascii=False, separators=(",", ":")
        )
        self._out.write(line + "\n")
        self._out.flush()

    async def __aenter__(self) -> TransportStreams:
        read, write = await self._inner.__aenter__()
        return _TapRead(read, self), _TapWrite(write, self)

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> bool | None:
        return await self._inner.__aexit__(exc_type, exc, tb)


class _TapRead:
    """Read side: records each message the client receives."""

    def __init__(self, inner: ReadStream[SessionMessage | Exception], tap: Wiretap) -> None:
        self._inner = inner
        self._tap = tap

    async def receive(self) -> SessionMessage | Exception:
        item = await self._inner.receive()
        if isinstance(item, SessionMessage):  # transports also deliver parse errors as Exceptions
            self._tap.record("received", item)
        return item

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> SessionMessage | Exception:
        item = await self._inner.__anext__()
        if isinstance(item, SessionMessage):
            self._tap.record("received", item)
        return item

    async def aclose(self) -> None:
        await self._inner.aclose()

    async def __aenter__(self) -> Self:
        await self._inner.__aenter__()
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> bool | None:
        return await self._inner.__aexit__(exc_type, exc, tb)


class _TapWrite:
    """Write side: records each message after the client sends it."""

    def __init__(self, inner: WriteStream[SessionMessage], tap: Wiretap) -> None:
        self._inner = inner
        self._tap = tap

    async def send(self, item: SessionMessage, /) -> None:
        await self._inner.send(item)
        self._tap.record("sent", item)

    async def aclose(self) -> None:
        await self._inner.aclose()

    async def __aenter__(self) -> Self:
        await self._inner.__aenter__()
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> bool | None:
        return await self._inner.__aexit__(exc_type, exc, tb)
