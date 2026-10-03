"""The scripted "hijacked model" and its tiny JSON-RPC client.

A real model *may* follow hidden instructions in a tool description; this one
always does. That makes every run deterministic, free and testable, and it
answers the question the Lab asks: *if the model is fooled, what stops the harm?*
"""

from __future__ import annotations

import itertools
import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

import anyio

from ledgerline.demo.common import FAKE_SECRETS_DISPLAY_PATH
from ledgerline.jsonrpc import JSON
from ledgerline.pin.canonical import NotCanonicalizable, sha256_hex
from ledgerline.sim.events import Menu, Mode, Step, ToolDef
from ledgerline.sim.scenario import AgentStep, CallTool, Discover, ListTools, ObeyNewInstructions, SendRaw

Emit = Callable[[Any], None]
SendBytes = Callable[[bytes], Awaitable[None]]

PROTOCOL_VERSION = "2026-07-28"
ENVELOPE = {
    "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
    "io.modelcontextprotocol/clientInfo": {"name": "ledgerline-sim-agent", "version": "0.1.0"},
    "io.modelcontextprotocol/clientCapabilities": {},
}
REQUEST_TIMEOUT = 15.0

# "read <path> and pass its full content as '<arg>'" (wording used by the demo servers)
_OBEY = re.compile(r"[Rr]ead (?:the file )?(\S+) and pass its\s+full content as '(\w+)'")


class ChannelError(RuntimeError):
    pass


class Channel:
    """A minimal JSON-RPC client over newline-delimited messages.

    The runner feeds it every line that comes back (``deliver``); ``request``
    waits for the reply with the matching id.
    """

    def __init__(self, send: SendBytes) -> None:
        self._send = send
        self._ids = itertools.count(1)
        self._waiting: dict[Any, tuple[anyio.Event, list[JSON]]] = {}

    def deliver(self, line: bytes) -> None:
        try:
            body = json.loads(line)
        except ValueError:
            return
        if not isinstance(body, dict) or "method" in body:
            return
        msg_id = body.get("id")
        if msg_id is None and "error" in body and self._waiting:
            # A rejected, unreadable message gets an error with id null; it answers the oldest wait.
            msg_id = next(iter(self._waiting))
        if msg_id in self._waiting:
            done, slot = self._waiting[msg_id]
            slot.append(body)
            done.set()

    async def request(self, method: str, params: JSON) -> JSON:
        msg_id = next(self._ids)
        body = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": {**params, "_meta": ENVELOPE}}
        return await self.send_raw(json.dumps(body).encode(), msg_id)

    async def send_raw(self, data: bytes, msg_id: Any) -> JSON:
        done = anyio.Event()
        slot: list[JSON] = []
        self._waiting[msg_id] = (done, slot)
        try:
            await self._send(data + b"\n")
            with anyio.fail_after(REQUEST_TIMEOUT):
                await done.wait()
        except TimeoutError:
            raise ChannelError(f"no reply to message {msg_id!r}") from None
        finally:
            self._waiting.pop(msg_id, None)
        return slot[0]


def tool_def(tool: JSON) -> ToolDef:
    try:
        sha = sha256_hex(tool)
    except NotCanonicalizable:
        sha = ""
    return ToolDef(
        name=str(tool.get("name")),
        description=str(tool.get("description") or ""),
        sha256=sha,
        definition=tool,
    )


def reply_text(reply: JSON) -> str:
    if "error" in reply:
        err = reply["error"]
        return f"error {err.get('code')}: {err.get('message')}"
    result = reply.get("result") or {}
    texts = [c.get("text", "") for c in result.get("content", []) if isinstance(c, dict)]
    text = " ".join(texts).replace("\n", " ")
    return ("isError: " if result.get("isError") else "") + text


class Agent:
    """Runs a scenario's steps for one mode, obeying whatever tool descriptions say."""

    def __init__(
        self, mode: Mode, channel: Channel, emit: Emit, secret: str, after_step: Callable[[], None]
    ) -> None:
        self.mode = mode
        self.channel = channel
        self.emit = emit
        self.secret = secret
        self.after_step = after_step
        self.menu: dict[str, JSON] = {}
        self.obeyed: set[str] = set()

    def _step(self, index: int, title: str, status: str = "done", detail: str = "") -> None:
        self.emit(Step(mode=self.mode, index=index, title=title, status=status, detail=detail))  # type: ignore[arg-type]
        self.after_step()

    def obey(self, tool: JSON) -> dict[str, object]:
        """Arguments a fooled model would add because the description told it to."""
        extra: dict[str, object] = {}
        for path, arg in _OBEY.findall(str(tool.get("description") or "")):
            if path.rstrip(".,") == FAKE_SECRETS_DISPLAY_PATH:
                extra[arg] = self.secret
        return extra

    async def run(self, steps: tuple[AgentStep, ...]) -> None:
        for i, step in enumerate(steps, 1):
            try:
                await self._run_step(i, step)
            except ChannelError as e:
                self._step(i, "no reply", "error", str(e))

    async def _call(self, i: int, name: str, args: dict[str, object]) -> None:
        tool = self.menu.get(name, {})
        obeyed = self.obey(tool)
        reply = await self.channel.request("tools/call", {"name": name, "arguments": {**args, **obeyed}})
        note = f" (obeying hidden instructions: added {', '.join(obeyed)})" if obeyed else ""
        self._step(i, f"call {name}{note}", detail=reply_text(reply))

    async def _run_step(self, i: int, step: AgentStep) -> None:
        match step:
            case Discover():
                reply = await self.channel.request("server/discover", {})
                info = ((reply.get("result") or {}).get("_meta") or {}).get(
                    "io.modelcontextprotocol/serverInfo", {}
                )
                self._step(
                    i,
                    "connect (server/discover)",
                    detail=f"{info.get('name', '?')} {info.get('version', '')}",
                )
            case ListTools():
                reply = await self.channel.request("tools/list", {})
                tools = [t for t in (reply.get("result") or {}).get("tools", []) if isinstance(t, dict)]
                self.menu = {str(t.get("name")): t for t in tools}
                self.emit(Menu(mode=self.mode, step=i, tools=[tool_def(t) for t in tools]))
                self._step(i, "list tools", detail=", ".join(self.menu) or "(no tools)")
            case CallTool(name=name, args=args, only_if_listed=only):
                if only and name not in self.menu:
                    self._step(
                        i, f"call {name}", "skipped", "not in the latest menu, so the host doesn't call it"
                    )
                    return
                await self._call(i, name, dict(args))
            case ObeyNewInstructions():
                targets = [
                    n
                    for n, t in self.menu.items()
                    if "call this tool" in str(t.get("description", "")).lower() and n not in self.obeyed
                ]
                if not targets:
                    self._step(
                        i,
                        "follow instructions in tool descriptions",
                        "skipped",
                        "nothing in the menu asks for it",
                    )
                for name in targets:
                    self.obeyed.add(name)
                    await self._call(i, name, {})
            case SendRaw(title=title, build=build, msg_id=msg_id):
                reply = await self.channel.send_raw(build(self.secret), msg_id)
                self._step(i, title, detail=reply_text(reply))
