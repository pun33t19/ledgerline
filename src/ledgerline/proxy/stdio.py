"""The stdio relay: ``ledgerline proxy stdio -- <server command>``.

The MCP host starts *Ledgerline* instead of the server; Ledgerline starts the
real server as its own child process and sits on the pipes in between::

    host ──stdin──► ledgerline ──stdin──► server
    host ◄─stdout── ledgerline ◄─stdout── server
                       (server stderr passes straight through)

Two loops run at once, one per direction. Each message (one JSON line) is
parsed and shown to the interceptor chain. Unless an interceptor changes or
blocks it, the *original bytes* are forwarded, so the relay is transparent.
"""

from __future__ import annotations

import itertools
import logging
import secrets
import subprocess
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field

import anyio
import anyio.abc
from anyio.streams.buffered import BufferedByteReceiveStream

from ledgerline.jsonrpc import (
    INVALID_REQUEST,
    JSON,
    MAX_MESSAGE_BYTES,
    Id,
    Kind,
    Message,
    ParseError,
    encode,
    error_response,
    parse,
)
from ledgerline.proxy.events import CONTROL_PARSING, NO_EVENTS, ProxyEvents
from ledgerline.proxy.interceptor import Block, Interceptor, Replace, UpstreamError

log = logging.getLogger("ledgerline.proxy")

SendBytes = Callable[[bytes], Awaitable[None]]

# How long the proxy waits for the server to answer a request of its own.
UPSTREAM_TIMEOUT_SECONDS = 30.0
# How long to wait for the server to exit after the client hangs up.
SHUTDOWN_GRACE_SECONDS = 5.0


class OversizedLine:
    """Marker yielded in place of a line longer than MAX_MESSAGE_BYTES (which was discarded)."""


Line = bytes | OversizedLine


@dataclass
class _Waiter:
    done: anyio.Event = field(default_factory=anyio.Event)
    response: Message | None = None


class _StdioUpstream:
    """Sends the proxy's own requests to the server and catches the replies.

    Their ids carry a random prefix so they can't collide with the client's,
    and their replies are consumed here, never forwarded to the client.
    """

    def __init__(
        self, send_to_server: SendBytes, chain: Interceptor, timeout: float, events: ProxyEvents
    ) -> None:
        self._send = send_to_server
        self._chain = chain
        self._events = events
        self._timeout = timeout
        self._prefix = f"ledgerline-{secrets.token_hex(4)}-"
        self._counter = itertools.count(1)
        self.pending: dict[Id, _Waiter] = {}

    async def request(self, method: str, params: JSON, *, like: Message) -> JSON:
        request_id = f"{self._prefix}{next(self._counter)}"
        waiter = self.pending[request_id] = _Waiter()
        body: JSON = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        try:
            data = encode(body)
            message = parse(data.rstrip(b"\n"))
            self._chain.observe("proxy→server", message)
            self._events.message("proxy→server", message, data, internal=True)
            await self._send(data)
            with anyio.fail_after(self._timeout):
                await waiter.done.wait()
        except TimeoutError:
            raise UpstreamError(f"no answer to {method} within {self._timeout:g}s") from None
        finally:
            self.pending.pop(request_id, None)

        response = waiter.response
        if response is None or response.result is None:
            error = response.body.get("error") if response else "no response"
            raise UpstreamError(f"{method} failed: {error}")
        return response.result

    def resolve(self, response: Message) -> bool:
        """Deliver a reply to one of our own requests. Returns False if it isn't ours."""
        waiter = self.pending.get(response.id) if response.id is not None else None
        if waiter is None:
            return False
        waiter.response = response
        waiter.done.set()
        return True


class StdioProxy:
    def __init__(
        self,
        command: list[str],
        chain: Interceptor,
        *,
        upstream_timeout: float = UPSTREAM_TIMEOUT_SECONDS,
        events: ProxyEvents = NO_EVENTS,
        strict_parsing: bool = True,
        env: dict[str, str] | None = None,
    ):
        if not command:
            raise ValueError("no server command given")
        self.command = command
        self.chain = chain
        self.upstream_timeout = upstream_timeout
        self.events = events
        self.strict_parsing = strict_parsing
        self.env = env

    async def run(self, client_lines: AsyncIterator[Line], send_to_client: SendBytes) -> int:
        """Relay until either side hangs up. Returns the server's exit code."""
        process = await anyio.open_process(
            self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None, env=self.env
        )
        if process.stdin is None or process.stdout is None:
            raise RuntimeError("server process has no stdin/stdout pipes")
        server_in, server_out = process.stdin, process.stdout

        to_client_lock, to_server_lock = anyio.Lock(), anyio.Lock()

        async def to_client(data: bytes) -> None:
            async with to_client_lock:
                await send_to_client(data)

        async def to_server(data: bytes) -> None:
            async with to_server_lock:
                await server_in.send(data)

        events = self.events
        upstream = _StdioUpstream(to_server, self.chain, self.upstream_timeout, events)
        # Client requests forwarded to the server and not yet answered, by id.
        pending: dict[Id, Message] = {}

        async def client_to_server() -> None:
            async for line in client_lines:
                if isinstance(line, OversizedLine):
                    events.message("client→proxy", None, b"")
                    events.decision("rejected", CONTROL_PARSING, "message too large", None)
                    await self._reply(to_client, error_response(None, INVALID_REQUEST, "message too large"))
                    continue
                try:
                    message = parse(line.rstrip(b"\r\n"), strict=self.strict_parsing)
                except ParseError as e:
                    # Never forward something we couldn't read: the server might read it differently.
                    events.message("client→proxy", None, line)
                    events.decision("rejected", CONTROL_PARSING, str(e), None)
                    await self._reply(to_client, error_response(None, e.code, str(e)))
                    continue

                events.message("client→proxy", message, line)
                self.chain.observe("client→server", message)
                if message.kind is not Kind.REQUEST:
                    events.message("proxy→server", message, line)
                    await to_server(line)  # notifications, and answers to the server's own requests
                    continue

                decision = await self.chain.on_request(message, upstream)
                if isinstance(decision, Block):
                    events.decision("blocked", decision.control, decision.reason, message)
                    await self._reply(to_client, decision.response)
                    continue
                if isinstance(decision, Replace):
                    events.decision("replaced", decision.control, decision.reason, message)
                    message = parse(encode(decision.body).rstrip(b"\n"))
                    line = encode(decision.body)
                if message.id is not None:
                    pending[message.id] = message
                events.message("proxy→server", message, line)
                await to_server(line)

        async def server_to_client() -> None:
            reader = BufferedByteReceiveStream(server_out)
            while True:
                try:
                    line = await reader.receive_until(b"\n", MAX_MESSAGE_BYTES) + b"\n"
                except (anyio.EndOfStream, anyio.IncompleteRead):
                    return
                except anyio.DelimiterNotFound:
                    log.error("server sent a message larger than %d bytes; stopping", MAX_MESSAGE_BYTES)
                    return
                try:
                    message = parse(line.rstrip(b"\r\n"))
                except ParseError as e:
                    log.error("dropping unreadable message from server: %s", e)
                    continue

                if message.kind is Kind.RESPONSE and upstream.resolve(message):
                    self.chain.observe("server→proxy", message)
                    events.message("server→proxy", message, line, internal=True)
                    continue
                self.chain.observe("server→client", message)
                events.message("server→proxy", message, line)

                request = (
                    pending.pop(message.id, None)
                    if message.kind is Kind.RESPONSE and message.id is not None
                    else None
                )
                outgoing = message
                if request is not None:
                    decision = await self.chain.on_response(request, message)
                    if isinstance(decision, Replace):
                        events.decision("replaced", decision.control, decision.reason, message)
                        line = encode(decision.body)
                        outgoing = parse(line.rstrip(b"\n"))
                        self.chain.observe("proxy→client", outgoing)
                    elif isinstance(decision, Block):
                        events.decision("blocked", decision.control, decision.reason, message)
                        line = encode(decision.response)
                        outgoing = parse(line.rstrip(b"\n"))
                        self.chain.observe("proxy→client", outgoing)
                events.message("proxy→client", outgoing, line)
                await to_client(line)

        try:
            async with anyio.create_task_group() as tg:

                async def watch_server() -> None:
                    await server_to_client()
                    tg.cancel_scope.cancel()  # server gone: stop reading from the client too

                tg.start_soon(watch_server)
                await client_to_server()
                # The client hung up: close the server's stdin so it exits, and
                # let the reader drain anything it still sends.
                await server_in.aclose()
                with anyio.move_on_after(SHUTDOWN_GRACE_SECONDS):
                    await process.wait()
                tg.cancel_scope.cancel()
        finally:
            if process.returncode is None:
                process.terminate()
            with anyio.CancelScope(shield=True):
                await process.wait()
        return process.returncode or 0

    async def _reply(self, to_client: SendBytes, body: JSON) -> None:
        data = encode(body)
        message = parse(data.rstrip(b"\n"))
        self.chain.observe("proxy→client", message)
        self.events.message("proxy→client", message, data)
        await to_client(data)


async def stdin_lines() -> AsyncIterator[Line]:
    """Read newline-delimited messages from this process's stdin.

    Blocking reads run in a worker thread so they don't stall the event loop.
    ``readline(limit)`` caps how much one line can occupy in memory.
    """
    stdin = sys.stdin.buffer

    async def read(limit: int) -> bytes:
        return await anyio.to_thread.run_sync(stdin.readline, limit)

    while True:
        line = await read(MAX_MESSAGE_BYTES + 1)
        if not line:
            return
        if not line.endswith(b"\n") and len(line) > MAX_MESSAGE_BYTES:
            # Too long: discard the rest of this line, then report it.
            while (more := await read(MAX_MESSAGE_BYTES)) and not more.endswith(b"\n"):
                pass
            yield OversizedLine()
            continue
        yield line if line.endswith(b"\n") else line + b"\n"


async def write_stdout(data: bytes) -> None:
    stdout = sys.stdout.buffer
    await anyio.to_thread.run_sync(lambda: (stdout.write(data), stdout.flush()))
