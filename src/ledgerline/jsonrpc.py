"""JSON-RPC 2.0 message handling for the proxy.

MCP messages are JSON-RPC 2.0. There are three kinds:

- **request**: has ``method`` and ``id``; the other side must answer.
- **notification**: has ``method`` but no ``id``; no answer expected.
- **response**: has ``id`` and exactly one of ``result`` or ``error``.

The proxy parses every message to decide what to do, but forwards the
*original bytes* whenever it doesn't change anything, so it never alters what
either side sent.

Parsing is deliberately strict. A security proxy that reads a message
differently from the server it protects can be bypassed ("parser
differential"), so anything ambiguous is rejected rather than guessed at:
duplicate keys, ``NaN``/``Infinity``, batches, and invalid UTF-8.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

# Standard JSON-RPC 2.0 error codes.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Lines longer than this are rejected, so one huge message can't exhaust memory.
MAX_MESSAGE_BYTES = 16 * 1024 * 1024

Id = str | int
JSON = dict[str, Any]


class Kind(Enum):
    REQUEST = "request"
    NOTIFICATION = "notification"
    RESPONSE = "response"


class ParseError(ValueError):
    """A message that is not valid JSON-RPC 2.0. ``code`` is the JSON-RPC error code to report."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Message:
    """A parsed JSON-RPC message, plus the exact bytes it arrived as."""

    kind: Kind
    body: JSON
    raw: bytes

    @property
    def id(self) -> Id | None:
        value = self.body.get("id")
        return value if isinstance(value, str | int) else None

    @property
    def method(self) -> str | None:
        value = self.body.get("method")
        return value if isinstance(value, str) else None

    @property
    def params(self) -> JSON:
        value = self.body.get("params")
        return value if isinstance(value, dict) else {}

    @property
    def result(self) -> JSON | None:
        value = self.body.get("result")
        return value if isinstance(value, dict) else None


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> JSON:
    obj: JSON = {}
    for key, value in pairs:
        if key in obj:
            raise ParseError(PARSE_ERROR, f"duplicate key {key!r}")
        obj[key] = value
    return obj


def _reject_constant(name: str) -> Any:
    raise ParseError(PARSE_ERROR, f"{name} is not valid JSON")


def _is_valid_id(value: Any) -> bool:
    # bool is a subclass of int in Python, but true/false are not valid ids.
    return isinstance(value, str) or (isinstance(value, int) and not isinstance(value, bool))


def parse(raw: bytes, *, strict: bool = True) -> Message:
    """Parse one JSON-RPC message. Raises :class:`ParseError` if it isn't valid.

    ``strict=False`` turns off the duplicate-key and NaN/Infinity checks, so
    the attack simulator can show what they protect against. Never in production.
    """
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ParseError(INVALID_REQUEST, f"message larger than {MAX_MESSAGE_BYTES} bytes")
    try:
        text = raw.decode("utf-8")
        if strict:
            body = json.loads(text, object_pairs_hook=_reject_duplicates, parse_constant=_reject_constant)
        else:
            body = json.loads(text)
    except ParseError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as e:
        raise ParseError(PARSE_ERROR, f"invalid JSON: {e}") from None

    if isinstance(body, list):
        # Batching was removed from MCP in 2025-06-18; refusing it keeps one message = one decision.
        raise ParseError(INVALID_REQUEST, "JSON-RPC batches are not supported")
    if not isinstance(body, dict):
        raise ParseError(INVALID_REQUEST, "message must be a JSON object")
    if body.get("jsonrpc") != "2.0":
        raise ParseError(INVALID_REQUEST, 'missing "jsonrpc": "2.0"')

    if "method" in body:
        if not isinstance(body["method"], str):
            raise ParseError(INVALID_REQUEST, "method must be a string")
        if "params" in body and not isinstance(body["params"], dict | list):
            raise ParseError(INVALID_REQUEST, "params must be an object or array")
        if "id" not in body:
            return Message(Kind.NOTIFICATION, body, raw)
        if not _is_valid_id(body["id"]):
            raise ParseError(INVALID_REQUEST, "request id must be a string or integer")
        return Message(Kind.REQUEST, body, raw)

    has_result, has_error = "result" in body, "error" in body
    if has_result == has_error:
        raise ParseError(INVALID_REQUEST, "response must have exactly one of result or error")
    if body.get("id") is not None and not _is_valid_id(body["id"]):
        raise ParseError(INVALID_REQUEST, "response id must be a string, integer or null")
    return Message(Kind.RESPONSE, body, raw)


def encode(body: JSON) -> bytes:
    """Serialise a message we build ourselves (compact, UTF-8, newline-terminated)."""
    return json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"


def error_response(id: Id | None, code: int, message: str) -> JSON:
    """A JSON-RPC protocol error, for messages that are malformed or not allowed at all."""
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


def tool_error_result(request: Message, text: str) -> JSON:
    """A ``tools/call`` result with ``isError: true``.

    Used when a well-formed call is refused. It is a *tool-level* error, so the
    model sees the explanation and can carry on, rather than the connection failing.
    """
    result: JSON = {"content": [{"type": "text", "text": text}], "isError": True}
    if is_modern(request):
        result["resultType"] = "complete"  # required on 2026-07-28 results
    return {"jsonrpc": "2.0", "id": request.id, "result": result}


# Keys of the 2026-07-28 per-request envelope carried in params._meta.
ENVELOPE_PREFIX = "io.modelcontextprotocol/"


def is_modern(message: Message) -> bool:
    """True if the request uses the 2026-07-28 per-request envelope."""
    meta = message.params.get("_meta")
    return isinstance(meta, dict) and any(str(k).startswith(ENVELOPE_PREFIX) for k in meta)


def envelope(message: Message) -> JSON:
    """The 2026-07-28 envelope (protocol version, client info, capabilities) from ``params._meta``.

    Requests the proxy sends on its own copy this, so the server treats them
    like the client's. Other ``_meta`` keys (e.g. progress tokens) are not copied.
    """
    meta = message.params.get("_meta")
    if not isinstance(meta, dict):
        return {}
    return {k: v for k, v in meta.items() if str(k).startswith(ENVELOPE_PREFIX)}
