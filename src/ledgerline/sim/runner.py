"""Runs one scenario, unprotected and protected at the same time, and reports events."""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import tempfile
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any, Literal

import anyio
import anyio.abc
from anyio.streams.buffered import BufferedByteReceiveStream

from ledgerline.demo.common import SECRETS_ENV
from ledgerline.jsonrpc import JSON, Kind, Message
from ledgerline.ledger.digest import Digester
from ledgerline.ledger.interceptor import LedgerInterceptor
from ledgerline.ledger.schema import Entry
from ledgerline.ledger.store import MemoryStore
from ledgerline.pin.interceptor import PinInterceptor
from ledgerline.pin.lockfile import Lockfile, PinnedTool
from ledgerline.proxy.events import Action, Hop, ProxyEvents
from ledgerline.proxy.interceptor import Chain, Interceptor
from ledgerline.proxy.stdio import StdioProxy
from ledgerline.sim.agent import Agent, Channel, tool_def
from ledgerline.sim.events import (
    Alert,
    Controls,
    Decision,
    Exfiltration,
    LedgerEntry,
    MessageEvent,
    Mode,
    Node,
    Outcome,
    Pinned,
)
from ledgerline.sim.scenario import Discover, ListTools, Scenario

FAKE_SECRET = "FAKE_API_KEY=demo-not-a-real-key"  # noqa: S105 - deliberately fake bait value
LAB_USER = "lab-visitor"
RUN_TIMEOUT = 60.0

_HOPS: dict[Hop, tuple[Node, Node]] = {
    "client→proxy": ("host", "ledgerline"),
    "proxy→server": ("ledgerline", "server"),
    "server→proxy": ("server", "ledgerline"),
    "proxy→client": ("ledgerline", "host"),
}


def _short(value: Any, limit: int = 70) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 1] + "…"


Kind_ = Literal["request", "notification", "response", "invalid"]


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def server_label(command: list[str]) -> str:
    """'demo-rugpull --after 3' for `python -m ledgerline.demo.servers.rugpull --after 3 --exfil-log …`."""
    module = command[2].rsplit(".", 1)[-1] if len(command) > 2 else command[0]
    args = command[3:]
    if "--exfil-log" in args:
        args = args[: args.index("--exfil-log")]
    return " ".join([f"demo-{module}", *args])


def summarize(body: Any) -> tuple[Kind_, str, str | None, Any]:
    """(kind, summary, method, id) for a JSON-RPC body, in plain words for the timeline."""
    if not isinstance(body, dict):
        return "invalid", "unreadable message", None, None
    method, msg_id = body.get("method"), body.get("id")
    if isinstance(method, str):
        params = _dict(body.get("params"))
        if method == "tools/call":
            args = params.get("arguments") or {}
            return "request", f"tools/call {params.get('name')} {_short(args, 60)}", method, msg_id
        return ("request" if "id" in body else "notification"), method, method, msg_id
    if "error" in body:
        err = _dict(body["error"])
        return "response", f"error {err.get('code')}: {_short(err.get('message', ''))}", None, msg_id
    result = _dict(body.get("result"))
    if "tools" in result:
        names = [str(t.get("name")) for t in result["tools"] if isinstance(t, dict)]
        return "response", f"{len(names)} tool(s): {', '.join(names) or '—'}", None, msg_id
    if "content" in result:
        text = " ".join(c.get("text", "") for c in result["content"] if isinstance(c, dict)).replace(
            "\n", " "
        )
        prefix = "isError: " if result.get("isError") else ""
        return "response", prefix + _short(text), None, msg_id
    return "response", "result", None, msg_id


def _pipes(process: anyio.abc.Process) -> tuple[anyio.abc.ByteSendStream, anyio.abc.ByteReceiveStream]:
    if process.stdin is None or process.stdout is None:
        raise RuntimeError("server process has no stdin/stdout pipes")
    return process.stdin, process.stdout


def _body(raw: bytes) -> Any:
    try:
        return json.loads(raw)
    except ValueError:
        return raw.decode("utf-8", "replace")[:500]


class _SimEvents(ProxyEvents):
    """Turns the proxy's reports into run events for the protected side."""

    def __init__(self, emit: Callable[[Any], None]) -> None:
        self.emit = emit
        self.stopped_by: set[str] = set()

    def message(self, hop: Hop, message: Message | None, raw: bytes, *, internal: bool = False) -> None:
        source, target = _HOPS[hop]
        body = message.body if message else _body(raw)
        kind: Kind_
        kind, summary, method, msg_id = (
            summarize(body) if message else ("invalid", "unreadable message", None, None)
        )
        if message and message.kind is Kind.NOTIFICATION:
            kind = "notification"
        self.emit(
            MessageEvent(
                mode="protected",
                source=source,
                target=target,
                internal=internal,
                kind=kind,
                method=method,
                msg_id=msg_id,
                summary=summary,
                body=body,
            )
        )

    def decision(self, action: Action, control: str, reason: str, message: Message | None) -> None:
        self.stopped_by.add(control)
        self.emit(
            Decision(
                mode="protected",
                action=action,
                control=control,
                reason=reason,
                method=message.method if message else None,
            )
        )

    def alert(self, event: JSON) -> None:
        details = {k: v for k, v in event.items() if k not in ("event", "tool")}
        self.emit(
            Alert(mode="protected", event=str(event.get("event")), tool=event.get("tool"), details=details)
        )


class _ExfilWatcher:
    """Reports new lines in a server's attacker log as exfiltration events."""

    def __init__(self, path: Path, mode: Mode, emit: Callable[[Any], None]) -> None:
        self.path, self.mode, self.emit = path, mode, emit
        self.seen = 0

    def poll(self) -> None:
        with contextlib.suppress(FileNotFoundError):
            lines = self.path.read_text(encoding="utf-8").splitlines()
            for line in lines[self.seen :]:
                via, _, data = line.partition("\t")
                self.emit(Exfiltration(mode=self.mode, via=via, data=data))
            self.seen = len(lines)


async def _lines(stream: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    async for chunk in stream:
        yield chunk


async def _pump_process(
    stdout: Any, deliver: Callable[[bytes], None], on_line: Callable[[bytes], None]
) -> None:
    reader = BufferedByteReceiveStream(stdout)
    while True:
        try:
            line = await reader.receive_until(b"\n", 16 * 1024 * 1024)
        except (anyio.EndOfStream, anyio.IncompleteRead):
            return
        on_line(line)
        deliver(line)


class Runner:
    """Executes one scenario with the given controls. ``emit`` receives every event in order."""

    def __init__(self, scenario: Scenario, controls: Controls, emit: Callable[[Any], None]) -> None:
        self.scenario = scenario
        self.controls = controls
        self._emit = emit
        self._start = time.monotonic()
        self._seq = 0
        self.ledger = MemoryStore()  # the protected side's ledger, for this run only
        self.ledger_run = f"lab-{scenario.id}-{os.urandom(3).hex()}"

    def emit(self, event: Any) -> None:
        self._seq += 1
        event.seq = self._seq
        event.t_ms = int((time.monotonic() - self._start) * 1000)
        self._emit(event)

    async def run(self) -> dict[Mode, Outcome]:
        with tempfile.TemporaryDirectory(prefix="ledgerline-sim-") as tmp:
            work = Path(tmp)
            secrets = work / "fake-secrets.txt"
            secrets.write_text(FAKE_SECRET + "\n", encoding="utf-8")
            env = {**os.environ, SECRETS_ENV: str(secrets)}
            outcomes: dict[Mode, Outcome] = {}

            with anyio.fail_after(RUN_TIMEOUT):
                lock = await self._pin(work, env) if self.controls.pinning else None
                async with anyio.create_task_group() as tg:

                    async def run_mode(mode: Mode) -> None:
                        outcomes[mode] = await self._run_mode(mode, work, env, lock)

                    tg.start_soon(run_mode, "unprotected")
                    tg.start_soon(run_mode, "protected")
            return outcomes

    async def _pin(self, work: Path, env: dict[str, str]) -> Lockfile:
        """What `ledgerline pin` would record: the server's tools as first installed."""
        process = await anyio.open_process(
            self.scenario.server(work / "pin-exfil.log"),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        stdin, stdout = _pipes(process)
        channel = Channel(stdin.send)
        tools: list[JSON] = []
        async with anyio.create_task_group() as tg:
            tg.start_soon(_pump_process, stdout, channel.deliver, lambda _l: None)
            await channel.request("server/discover", {})
            reply = await channel.request("tools/list", {})
            tools = [t for t in (reply.get("result") or {}).get("tools", []) if isinstance(t, dict)]
            await stdin.aclose()
            with anyio.move_on_after(5):
                await process.wait()
            tg.cancel_scope.cancel()
        if process.returncode is None:
            process.terminate()
        self.emit(Pinned(tools=[tool_def(t) for t in tools]))
        return Lockfile(tools={str(t["name"]): PinnedTool.of(t) for t in tools}, server={})

    async def _run_mode(self, mode: Mode, work: Path, env: dict[str, str], lock: Lockfile | None) -> Outcome:
        exfil = _ExfilWatcher(work / f"exfil-{mode}.log", mode, self.emit)
        command = self.scenario.server(exfil.path)
        steps = self.scenario.steps
        if not any(isinstance(s, Discover) for s in steps[:1]):
            steps = (Discover(), ListTools(), *steps)

        if mode == "unprotected":
            stopped_by = await self._direct(command, env, steps, exfil)
        else:
            stopped_by = await self._through_proxy(command, env, steps, exfil, lock)

        exfil.poll()
        if exfil.seen:
            outcome = Outcome(
                mode=mode,
                verdict="harmed",
                headline="The attacker received the secret",
                stopped_by=sorted(stopped_by),
            )
        elif stopped_by:
            outcome = Outcome(
                mode=mode, verdict="safe", headline="Stopped by Ledgerline", stopped_by=sorted(stopped_by)
            )
        else:
            outcome = Outcome(mode=mode, verdict="safe", headline="No harm done")
        self.emit(outcome)
        return outcome

    async def _direct(
        self, command: list[str], env: dict[str, str], steps: tuple[Any, ...], exfil: _ExfilWatcher
    ) -> set[str]:
        process = await anyio.open_process(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env
        )
        stdin, stdout = _pipes(process)

        def report(source: Node, target: Node, raw: bytes) -> None:
            body = _body(raw)
            kind, summary, method, msg_id = summarize(body)
            self.emit(
                MessageEvent(
                    mode="unprotected",
                    source=source,
                    target=target,
                    kind=kind,
                    method=method,
                    msg_id=msg_id,
                    summary=summary,
                    body=body,
                )
            )

        async def send(data: bytes) -> None:
            report("host", "server", data.rstrip(b"\n"))
            await stdin.send(data)

        channel = Channel(send)
        agent = Agent("unprotected", channel, self.emit, FAKE_SECRET, exfil.poll)
        async with anyio.create_task_group() as tg:
            tg.start_soon(_pump_process, stdout, channel.deliver, lambda line: report("server", "host", line))
            await agent.run(steps)
            await stdin.aclose()
            with anyio.move_on_after(5):
                await process.wait()
            tg.cancel_scope.cancel()
        if process.returncode is None:
            process.terminate()
        return set()

    async def _through_proxy(
        self,
        command: list[str],
        env: dict[str, str],
        steps: tuple[Any, ...],
        exfil: _ExfilWatcher,
        lock: Lockfile | None,
    ) -> set[str]:
        events = _SimEvents(self.emit)
        interceptors: list[Interceptor] = []
        if lock is not None:
            interceptors.append(
                PinInterceptor(lock, verify_each_call=self.controls.verify_each_call, on_alert=events.alert)
            )

        def pinned_hash(name: str) -> str | None:
            pin = lock.tools.get(name) if lock else None
            return pin.sha256 if pin else None

        ledger = LedgerInterceptor(
            Chain(interceptors),
            self.ledger,
            run_id=self.ledger_run,
            server=server_label(command),
            digester=Digester.random(),
            user=LAB_USER,
            tool_hash=pinned_hash,
            on_entry=lambda e: self.emit(LedgerEntry(mode="protected", entry=Entry.model_validate(e))),
        )
        proxy = StdioProxy(
            command, ledger, events=events, strict_parsing=self.controls.strict_parsing, env=env
        )

        to_proxy_send, to_proxy_recv = anyio.create_memory_object_stream[bytes](64)
        to_host_send, to_host_recv = anyio.create_memory_object_stream[bytes](64)
        channel = Channel(to_proxy_send.send)
        agent = Agent("protected", channel, self.emit, FAKE_SECRET, exfil.poll)

        async def host_reader() -> None:
            async for data in to_host_recv:
                channel.deliver(data.rstrip(b"\n"))

        async with anyio.create_task_group() as tg:
            tg.start_soon(host_reader)
            proxy_done = anyio.Event()

            async def run_proxy() -> None:
                try:
                    await proxy.run(_lines(to_proxy_recv), to_host_send.send)
                finally:
                    proxy_done.set()

            tg.start_soon(run_proxy)
            await agent.run(steps)
            await to_proxy_send.aclose()  # the host hangs up; the proxy shuts the server down
            with anyio.move_on_after(8):
                await proxy_done.wait()
            tg.cancel_scope.cancel()
        return events.stopped_by
