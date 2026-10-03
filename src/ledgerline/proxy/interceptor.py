"""The plug-in point for checks: interceptors see every message and decide its fate.

For each client request the proxy asks the interceptor chain for a decision:

- :class:`Forward`: send the original bytes on, untouched.
- :class:`Replace`: send this modified message instead.
- :class:`Block`: don't send it; answer the client with this response instead.

Responses coming back from the server go through the chain too (so tool
listings can be inspected). Every later phase (ledger, policy, approvals,
telemetry) is another interceptor added to the chain.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from ledgerline.jsonrpc import JSON, Message, encode, parse

# Who sent a message to whom. "proxy" messages are ones Ledgerline itself created:
# its replies to the client (e.g. a block) and its own questions to the server.
Direction = Literal["client→server", "server→client", "proxy→client", "proxy→server", "server→proxy"]


@dataclass(frozen=True)
class Forward:
    """Pass the message on unchanged."""


@dataclass(frozen=True)
class Replace:
    """Pass this modified message on instead of the original."""

    body: JSON
    reason: str = ""
    control: str = ""  # which control made the change (see proxy/events.py)


@dataclass(frozen=True)
class Block:
    """Stop the message; send ``response`` back to whoever sent it."""

    response: JSON
    reason: str
    control: str = ""  # which control made the decision (see proxy/events.py)


Decision = Forward | Replace | Block
FORWARD = Forward()


class UpstreamError(RuntimeError):
    """A request the proxy sent to the server on its own behalf failed."""


class Upstream(Protocol):
    """Lets an interceptor ask the real server something before deciding.

    Implemented by each transport. ``like`` is the client request being
    decided; the transport copies its session details (protocol envelope,
    session id, auth) so the server treats the proxy's request like the client's.
    """

    async def request(self, method: str, params: JSON, *, like: Message) -> JSON:
        """Send a request to the server and return its ``result``; raise UpstreamError on failure."""
        ...


class Interceptor:
    """Base class: every hook defaults to "do nothing, forward"."""

    async def on_request(self, request: Message, upstream: Upstream) -> Decision:
        """A client→server request, before it is forwarded."""
        return FORWARD

    async def on_response(self, request: Message, response: Message) -> Decision:
        """A server→client response to ``request``, before it is forwarded."""
        return FORWARD

    def observe(self, direction: Direction, message: Message) -> None:
        """Every message in either direction, including ones the proxy generates. For logging."""


class Chain(Interceptor):
    """Runs several interceptors as one.

    Requests go through them in order and responses in reverse order, like
    layers of an onion. The first :class:`Block` wins; a :class:`Replace` is
    what the next interceptor sees.
    """

    def __init__(self, interceptors: Sequence[Interceptor]) -> None:
        self.interceptors = list(interceptors)

    async def on_request(self, request: Message, upstream: Upstream) -> Decision:
        return await self._run(request, lambda i, m: i.on_request(m, upstream), self.interceptors)

    async def on_response(self, request: Message, response: Message) -> Decision:
        return await self._run(response, lambda i, m: i.on_response(request, m), reversed(self.interceptors))

    def observe(self, direction: Direction, message: Message) -> None:
        for interceptor in self.interceptors:
            interceptor.observe(direction, message)

    @staticmethod
    async def _run(message: Message, call: _Hook, interceptors: Iterable[Interceptor]) -> Decision:
        decision: Decision = FORWARD
        for interceptor in interceptors:
            step = await call(interceptor, message)
            if isinstance(step, Block):
                return step
            if isinstance(step, Replace):
                decision = step
                message = parse(encode(step.body).rstrip(b"\n"))
        return decision


class _Hook(Protocol):
    async def __call__(self, interceptor: Interceptor, message: Message, /) -> Decision: ...
