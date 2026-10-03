"""Protection for Ledgerline's local web servers (the UI and `ledgerline proxy http`).

A web page you visit can make your browser send requests to `127.0.0.1`.
Two classic attacks follow from that, and both are blocked here:

- **DNS rebinding:** an attacker's domain is made to resolve to 127.0.0.1, so
  the browser treats the local server as "same origin" with the attacker's
  page. The request still carries the attacker's name in the `Host` header,
  so only the exact local names are accepted.
- **Cross-site requests:** another page posts to the local server. Browsers
  send an `Origin` header, which must be one we expect.

The UI additionally requires a random session token (printed by `ledgerline ui`,
like Jupyter) before any `/api` call is answered.
"""

from __future__ import annotations

import hmac
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

SESSION_COOKIE = "ledgerline_session"
LOOPBACK_NAMES = ("127.0.0.1", "localhost", "[::1]")

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; "
    "object-src 'none'"
)
SECURITY_HEADERS = [
    (b"content-security-policy", CSP.encode()),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
]


def loopback_hosts(port: int) -> set[str]:
    return {f"{name}:{port}" for name in LOOPBACK_NAMES}


def loopback_origins(port: int) -> set[str]:
    return {f"http://{name}:{port}" for name in LOOPBACK_NAMES}


def is_loopback(host: str) -> bool:
    return host in ("127.0.0.1", "localhost", "::1", "[::1]")


@dataclass
class LocalGuard:
    """Settings for :class:`LocalGuardMiddleware`.

    ``allowed_hosts`` empty = no Host check (only for deliberate non-loopback
    deployments behind their own network controls). ``token`` None = no
    session token (the proxy). ``open_paths`` are reachable without the token.
    """

    allowed_hosts: set[str]
    allowed_origins: set[str] = field(default_factory=set)
    token: str | None = None
    protected_prefix: str = "/api/"
    open_paths: frozenset[str] = frozenset({"/api/session", "/api/health"})
    add_security_headers: bool = True

    def token_ok(self, presented: Iterable[str]) -> bool:
        if self.token is None:
            return True
        return any(hmac.compare_digest(p.encode(), self.token.encode()) for p in presented if p)


def _headers(scope: Scope) -> dict[str, str]:
    return {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}


def _cookies(header: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in header.split(";"):
        name, _, value = part.strip().partition("=")
        if name:
            out[name] = value
    return out


class LocalGuardMiddleware:
    """ASGI middleware enforcing :class:`LocalGuard` on HTTP and WebSocket requests."""

    def __init__(self, app: ASGIApp, guard: LocalGuard) -> None:
        self.app = app
        self.guard = guard

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = _headers(scope)
        problem = self._check(scope, headers)
        if problem is not None:
            status, text = problem
            await _reject(scope, receive, send, status, text)
            return

        if scope["type"] == "http" and self.guard.add_security_headers:

            async def send_with_headers(message: Message) -> None:
                if message["type"] == "http.response.start":
                    message = {**message, "headers": [*message.get("headers", []), *SECURITY_HEADERS]}
                await send(message)

            await self.app(scope, receive, send_with_headers)
            return
        await self.app(scope, receive, send)

    def _check(self, scope: Scope, headers: dict[str, str]) -> tuple[int, str] | None:
        guard = self.guard
        host = headers.get("host", "").lower()
        if guard.allowed_hosts and host not in guard.allowed_hosts:
            return 403, "Host not allowed (possible DNS rebinding)"
        origin = headers.get("origin")
        if origin is not None and origin.lower() not in guard.allowed_origins:
            return 403, "Origin not allowed"
        path: str = scope.get("path", "")
        if path.startswith(guard.protected_prefix) and path not in guard.open_paths:
            bearer = headers.get("authorization", "").removeprefix("Bearer ").strip()
            cookie = _cookies(headers.get("cookie", "")).get(SESSION_COOKIE, "")
            if not guard.token_ok([bearer, cookie]):
                return 401, "Missing or invalid session token: open the link printed by `ledgerline ui`"
        return None


async def _reject(scope: Scope, receive: Receive, send: Send, status: int, text: str) -> None:
    if scope["type"] == "websocket":
        await send({"type": "websocket.close", "code": 4403 if status == 403 else 4401, "reason": text})
        return
    body = text.encode()
    start: dict[str, Any] = {
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"text/plain; charset=utf-8"),
            (b"content-length", str(len(body)).encode()),
            *SECURITY_HEADERS,
        ],
    }
    await send(start)
    await send({"type": "http.response.body", "body": body})
