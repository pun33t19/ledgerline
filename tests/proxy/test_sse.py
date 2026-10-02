from collections.abc import AsyncIterator

import pytest

from ledgerline.jsonrpc import MAX_MESSAGE_BYTES
from ledgerline.proxy.sse import EventTooLarge, event_data, split_events, with_data

pytestmark = pytest.mark.anyio


async def chunks(*parts: bytes) -> AsyncIterator[bytes]:
    for part in parts:
        yield part


async def test_split_events_across_chunk_boundaries() -> None:
    stream = chunks(b"event: message\nda", b'ta: {"a":1}\n\nda', b'ta: {"b":2}\r\n\r\n')
    events = [e async for e in split_events(stream)]
    assert events == [b'event: message\ndata: {"a":1}\n\n', b'data: {"b":2}\r\n\r\n']


async def test_oversized_event_is_refused() -> None:
    with pytest.raises(EventTooLarge):
        _ = [e async for e in split_events(chunks(b"data: " + b"x" * (MAX_MESSAGE_BYTES + 1)))]


def test_event_data_joins_multiple_lines() -> None:
    assert event_data(b'event: message\ndata: {"a":\ndata:1}\n\n') == b'{"a":\n1}'
    assert event_data(b": just a comment\n\n") is None


def test_with_data_keeps_other_fields() -> None:
    assert (
        with_data(b"event: message\nid: 7\ndata: old\n\n", b"new") == b"event: message\nid: 7\ndata: new\n\n"
    )
