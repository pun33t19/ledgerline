"""The Streamable HTTP proxy: ``ledgerline proxy http --upstream URL``.

Clients send their MCP requests to Ledgerline at ``/mcp``; Ledgerline checks
each one, forwards it to the real server with ``httpx``, inspects the reply
(plain JSON or a stream of server-sent events) and passes it back::

    client ──POST /mcp──► ledgerline ──POST──► upstream server
    client ◄─JSON / SSE── ledgerline ◄──────── upstream server

GET (the optional server→client event stream) and DELETE (ending a session)
are passed through.
"""

from __future__ import annotations

import contextlib
import itertools
import secrets
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

import httpx
from mcp.shared.inbound import NAME_BEARING_METHODS, decode_header_value
from mcp_types.jsonrpc import HEADER_MISMATCH
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from ledgerline.jsonrpc import (
    JSON,
    MAX_MESSAGE_BYTES,
    Kind,
    Message,
    ParseError,
    encode,
    error_response,
    parse,
)
from ledgerline.proxy.interceptor import Block, Interceptor, Replace, UpstreamError
from ledgerline.proxy.sse import event_data, split_events, with_data

UPSTREAM_TIMEOUT = httpx.Timeout(30.0, read=None)  # streams may stay open; per-request checks set their own
MODERN_PROTOCOL = "2026-07-28"

# Headers that describe one network hop, not the message; never forwarded (RFC 9110 §7.6.1).
_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)
_DROP_REQUEST = _HOP_BY_HOP | {"host", "content-length", "accept-encoding"}
_DROP_RESPONSE = _HOP_BY_HOP | {"content-length", "content-encoding"}
# Copied onto the proxy's own requests so the server treats them like the client's.
_SESSION_HEADERS = ("authorization", "mcp-session-id", "mcp-protocol-version")


def check_routing_headers(headers: Mapping[str, str], message: Message) -> str | None:
    """Return a problem if the ``Mcp-Method``/``Mcp-Name`` headers disagree with the body.

    2026-07-28 puts the method and tool name in headers so gateways can route
    without reading the body. If a header and the body disagree, a gateway
    could route on one while Ledgerline checks the other, so mismatches are
    rejected. On 2026-07-28 requests the headers are also required.
    """
    modern = headers.get("mcp-protocol-version", "") >= MODERN_PROTOCOL
    method_header = headers.get("mcp-method")
    if method_header is None:
        return "Mcp-Method header is required on 2026-07-28 requests" if modern else None
    if method_header != message.method:
        return "Mcp-Method header does not match the body's method"

    key = NAME_BEARING_METHODS.get(message.method or "")
    if key is None:
        return None
    value = message.params.get(key)
    name_header = headers.get("mcp-name")
    if name_header is None:
        return "Mcp-Name header is required for this method" if modern and value is not None else None
    if decode_header_value(name_header) != value:
        return f"Mcp-Name header does not match the body's {key!r}"
    return None


def _forward_headers(headers: Mapping[str, str]) -> dict[str, str]:
    out = {k: v for k, v in headers.items() if k.lower() not in _DROP_REQUEST}
    out["accept-encoding"] = "identity"  # the proxy must read bodies, so ask for them uncompressed
    return out


def _response_headers(response: httpx.Response) -> dict[str, str]:
    return {k: v for k, v in response.headers.items() if k.lower() not in _DROP_RESPONSE}


async def _messages_in(response: httpx.Response) -> AsyncIterator[Message]:
    """Every JSON-RPC message in an upstream reply, whether plain JSON or SSE."""
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        async for event in split_events(response.aiter_bytes()):
            if (data := event_data(event)) is not None:
                try:
                    yield parse(data)
                except ParseError:
                    continue
    else:
        yield parse(await response.aread())


class _HttpUpstream:
    """Sends the proxy's own requests to the upstream server, reusing the client's session details."""

    def __init__(
        self, client: httpx.AsyncClient, url: str, client_headers: Mapping[str, str], timeout: float
    ) -> None:
        self._client = client
        self._url = url
        self._session = {h: client_headers[h] for h in _SESSION_HEADERS if h in client_headers}
        self._timeout = timeout

    _counter = itertools.count(1)
    _prefix = f"ledgerline-{secrets.token_hex(4)}-"

    async def request(self, method: str, params: JSON, *, like: Message) -> JSON:
        request_id = f"{self._prefix}{next(self._counter)}"
        body: JSON = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        headers = {
            **self._session,
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
            "accept-encoding": "identity",
            "mcp-method": method,
        }
        try:
            async with self._client.stream(
                "POST", self._url, headers=headers, content=encode(body), timeout=self._timeout
            ) as response:
                if response.status_code >= 400:
                    raise UpstreamError(f"{method}: upstream HTTP {response.status_code}")
                async for message in _messages_in(response):
                    if message.kind is Kind.RESPONSE and message.id == request_id:
                        if message.result is None:
                            raise UpstreamError(f"{method} failed: {message.body.get('error')}")
                        return message.result
        except (httpx.HTTPError, ParseError) as e:
            raise UpstreamError(f"{method}: {e}") from e
        raise UpstreamError(f"{method}: no response from upstream")


class HttpProxy:
    def __init__(self, upstream_url: str, chain: Interceptor, *, check_timeout: float = 30.0) -> None:
        self.upstream_url = upstream_url
        self.chain = chain
        self.check_timeout = check_timeout
        self.client: httpx.AsyncClient | None = None

    def _client(self) -> httpx.AsyncClient:
        if self.client is None:
            raise RuntimeError("HttpProxy used outside its app lifespan")
        return self.client

    async def handle(self, request: Request) -> Response:
        if request.method == "POST":
            return await self._post(request)
        return await self._passthrough(request)  # GET event stream, DELETE session

    async def _post(self, request: Request) -> Response:
        body = await request.body()
        if len(body) > MAX_MESSAGE_BYTES:
            return JSONResponse(error_response(None, -32600, "message too large"), status_code=413)
        try:
            message = parse(body)
        except ParseError as e:
            return JSONResponse(error_response(None, e.code, str(e)), status_code=400)

        headers = {k.lower(): v for k, v in request.headers.items()}
        if message.kind is Kind.REQUEST and (problem := check_routing_headers(headers, message)):
            return self._reply(error_response(message.id, HEADER_MISMATCH, problem), status=400)

        self.chain.observe("client→server", message)
        if message.kind is Kind.REQUEST:
            upstream = _HttpUpstream(self._client(), self.upstream_url, headers, self.check_timeout)
            decision = await self.chain.on_request(message, upstream)
            if isinstance(decision, Block):
                return self._reply(decision.response)
            if isinstance(decision, Replace):
                body = encode(decision.body).rstrip(b"\n")
                message = parse(body)

        upstream_request = self._client().build_request(
            "POST", self.upstream_url, headers=_forward_headers(request.headers), content=body
        )
        response = await self._client().send(upstream_request, stream=True)
        content_type = response.headers.get("content-type", "")

        if message.kind is not Kind.REQUEST:
            return self._stream(response, None)  # e.g. 202 Accepted for notifications
        if content_type.startswith("text/event-stream"):
            return self._stream(response, message)
        data = await response.aread()
        await response.aclose()
        return Response(
            await self._inspect(message, data),
            status_code=response.status_code,
            headers=_response_headers(response),
        )

    async def _inspect(self, request: Message, data: bytes) -> bytes:
        """Run one upstream reply through the chain; return the bytes to send to the client."""
        try:
            message = parse(data.strip())
        except ParseError:
            return data
        self.chain.observe("server→client", message)
        if message.kind is not Kind.RESPONSE or message.id != request.id:
            return data
        decision = await self.chain.on_response(request, message)
        if isinstance(decision, Replace | Block):
            new = decision.body if isinstance(decision, Replace) else decision.response
            out = encode(new).rstrip(b"\n")
            self.chain.observe("proxy→client", parse(out))
            return out
        return data

    def _stream(self, response: httpx.Response, request: Message | None) -> StreamingResponse:
        """Pass an SSE stream through event by event, inspecting the reply to ``request``."""

        async def events() -> AsyncIterator[bytes]:
            try:
                if not response.headers.get("content-type", "").startswith("text/event-stream"):
                    async for chunk in response.aiter_raw():
                        yield chunk
                    return
                async for event in split_events(response.aiter_bytes()):
                    data = event_data(event)
                    if data is None or request is None:
                        if data is not None:
                            self._observe_raw(data)
                        yield event
                        continue
                    new = await self._inspect(request, data)
                    yield event if new is data else with_data(event, new)
            finally:
                await response.aclose()

        return StreamingResponse(
            events(), status_code=response.status_code, headers=_response_headers(response)
        )

    def _observe_raw(self, data: bytes) -> None:
        with contextlib.suppress(ParseError):
            self.chain.observe("server→client", parse(data))

    async def _passthrough(self, request: Request) -> Response:
        upstream_request = self._client().build_request(
            request.method,
            self.upstream_url,
            headers=_forward_headers(request.headers),
            content=await request.body(),
        )
        response = await self._client().send(upstream_request, stream=True)
        return self._stream(response, None)

    def _reply(self, body: JSON, status: int = 200) -> Response:
        data = encode(body).rstrip(b"\n")
        self.chain.observe("proxy→client", parse(data))
        return Response(data, status_code=status, media_type="application/json")


def build_app(upstream_url: str, chain: Interceptor) -> Starlette:
    proxy = HttpProxy(upstream_url, chain)

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT) as client:
            proxy.client = client
            yield
            proxy.client = None

    return Starlette(
        routes=[Route("/mcp", proxy.handle, methods=["GET", "POST", "DELETE"])], lifespan=lifespan
    )
