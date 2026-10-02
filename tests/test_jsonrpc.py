import contextlib
import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ledgerline.jsonrpc import (
    INVALID_REQUEST,
    MAX_MESSAGE_BYTES,
    PARSE_ERROR,
    Kind,
    ParseError,
    encode,
    envelope,
    is_modern,
    parse,
    tool_error_result,
)


@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        pytest.param(b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}', Kind.REQUEST, id="request-int-id"),
        pytest.param(
            b'{"jsonrpc":"2.0","id":"a","method":"x","params":{}}', Kind.REQUEST, id="request-str-id"
        ),
        pytest.param(
            b'{"jsonrpc":"2.0","method":"notifications/initialized"}', Kind.NOTIFICATION, id="notification"
        ),
        pytest.param(b'{"jsonrpc":"2.0","id":1,"result":{}}', Kind.RESPONSE, id="result"),
        pytest.param(
            b'{"jsonrpc":"2.0","id":null,"error":{"code":-1,"message":"x"}}',
            Kind.RESPONSE,
            id="error-null-id",
        ),
    ],
)
def test_classifies(raw: bytes, kind: Kind) -> None:
    message = parse(raw)
    assert message.kind is kind
    assert message.raw == raw


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        pytest.param(b"not json", PARSE_ERROR, id="not-json"),
        pytest.param(b"\xff\xfe", PARSE_ERROR, id="bad-utf8"),
        # Parser differential: Python keeps the last duplicate, other parsers keep the first.
        pytest.param(b'{"jsonrpc":"2.0","id":1,"method":"a","method":"b"}', PARSE_ERROR, id="duplicate-key"),
        pytest.param(b'{"jsonrpc":"2.0","id":1,"result":{"x":NaN}}', PARSE_ERROR, id="nan"),
        pytest.param(b'[{"jsonrpc":"2.0","id":1,"method":"a"}]', INVALID_REQUEST, id="batch"),
        pytest.param(b'"hello"', INVALID_REQUEST, id="not-object"),
        pytest.param(b'{"id":1,"method":"a"}', INVALID_REQUEST, id="missing-jsonrpc"),
        pytest.param(b'{"jsonrpc":"2.0","id":true,"method":"a"}', INVALID_REQUEST, id="bool-id"),
        pytest.param(b'{"jsonrpc":"2.0","id":1,"method":5}', INVALID_REQUEST, id="method-not-string"),
        pytest.param(
            b'{"jsonrpc":"2.0","id":1,"method":"a","params":5}', INVALID_REQUEST, id="params-scalar"
        ),
        pytest.param(
            b'{"jsonrpc":"2.0","id":1,"result":{},"error":{}}', INVALID_REQUEST, id="result-and-error"
        ),
        pytest.param(b'{"jsonrpc":"2.0","id":1}', INVALID_REQUEST, id="neither"),
    ],
)
def test_rejects(raw: bytes, code: int) -> None:
    with pytest.raises(ParseError) as exc:
        parse(raw)
    assert exc.value.code == code


def test_rejects_oversized() -> None:
    with pytest.raises(ParseError):
        parse(b" " * (MAX_MESSAGE_BYTES + 1))


@given(st.binary(max_size=512))
def test_never_crashes_on_arbitrary_bytes(raw: bytes) -> None:
    """Whatever arrives, the parser either understands it or raises ParseError, nothing else."""
    with contextlib.suppress(ParseError):
        parse(raw)


json_values = st.recursive(
    st.none() | st.booleans() | st.integers(-(2**53), 2**53) | st.text(max_size=20),
    lambda inner: st.lists(inner, max_size=4) | st.dictionaries(st.text(max_size=8), inner, max_size=4),
    max_leaves=12,
)


@given(
    request_id=st.integers(0, 2**31) | st.text(min_size=1, max_size=10),
    method=st.text(min_size=1, max_size=20),
    params=st.dictionaries(st.text(max_size=8), json_values, max_size=4),
)
def test_requests_round_trip(request_id: int | str, method: str, params: dict[str, object]) -> None:
    body = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    message = parse(encode(body).rstrip(b"\n"))
    assert message.kind is Kind.REQUEST
    assert message.body == body


MODERN_CALL = parse(
    json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "t",
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                    "io.modelcontextprotocol/clientCapabilities": {},
                    "progressToken": "p1",
                },
            },
        }
    ).encode()
)
LEGACY_CALL = parse(b'{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"t"}}')


def test_envelope_copies_only_protocol_keys() -> None:
    assert envelope(MODERN_CALL) == {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    assert envelope(LEGACY_CALL) == {}
    assert is_modern(MODERN_CALL)
    assert not is_modern(LEGACY_CALL)


def test_tool_error_result_matches_protocol() -> None:
    modern = tool_error_result(MODERN_CALL, "no")
    assert modern["id"] == 3
    assert modern["result"] == {
        "content": [{"type": "text", "text": "no"}],
        "isError": True,
        "resultType": "complete",
    }
    assert "resultType" not in tool_error_result(LEGACY_CALL, "no")["result"]
