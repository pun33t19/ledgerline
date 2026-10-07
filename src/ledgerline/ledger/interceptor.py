"""Write-before-forward: every ``tools/call`` is in the ledger before it runs (ADR-009).

The ledger wraps the rest of the interceptor chain rather than being one more
link in it. That way it records the *final* decision about each call, including
calls another control blocks (a blocked call never reaches later links):

    request ──► ledger ──► inner chain (pins, …) ──► decision
                  │ write "request" entry with the decision, commit
                  └──► only then is the call forwarded (or refused)

    response ──► inner chain ──► ledger: write "outcome" entry ──► client

If the request entry can't be written, the call is not forwarded: the client
gets a tool error instead (fail closed). A missing *outcome* entry can't undo a
call that already ran, so that failure is logged and the reply passes through.
"""

from __future__ import annotations

import getpass
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ledgerline.jsonrpc import JSON, Id, Message, tool_error_result
from ledgerline.ledger.digest import Digester
from ledgerline.ledger.schema import SCHEMA_VERSION
from ledgerline.ledger.store import LedgerStore
from ledgerline.proxy.events import CONTROL_LEDGER
from ledgerline.proxy.interceptor import Block, Decision, Direction, Interceptor, Replace, Upstream

log = logging.getLogger("ledgerline.ledger")

CLIENT_INFO = "io.modelcontextprotocol/clientInfo"


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _client_name(info: object) -> str | None:
    if not isinstance(info, dict) or not info.get("name"):
        return None
    return f"{info['name']} {info.get('version', '')}".strip()


class LedgerInterceptor(Interceptor):
    def __init__(
        self,
        inner: Interceptor,
        store: LedgerStore,
        *,
        run_id: str,
        server: str,
        digester: Digester,
        tenant: str = "default",
        user: str | None = None,
        tool_hash: Callable[[str], str | None] = lambda _name: None,
        keep_args: bool = False,
        on_entry: Callable[[JSON], None] = lambda _entry: None,
    ) -> None:
        self.inner = inner
        self.store = store
        self.run_id = run_id
        self.server = server
        self.digester = digester
        self.tenant = tenant
        self.user = user if user is not None else getpass.getuser()
        self.tool_hash = tool_hash
        self.keep_args = keep_args
        self.on_entry = on_entry
        self.agent: str | None = None  # learned from the client's clientInfo
        self._pending: dict[Id, tuple[str, str | None]] = {}  # request id → (request entry hash, tool)

    # --- the entry ------------------------------------------------------------

    def _fields(self, kind: str, tool: str | None) -> JSON:
        chain = [who for who in (self.user, self.agent) if who]
        return {
            "schema_version": SCHEMA_VERSION,
            "ts": now(),
            "run_id": self.run_id,
            "tenant": self.tenant,
            "kind": kind,
            "actor": {"user": self.user, "agent": self.agent, "on_behalf_of_chain": chain},
            "protocol": "mcp",
            "method": "tools/call",
            "server": self.server,
            "tool": tool,
            "tool_def_sha256": self.tool_hash(tool) if tool else None,
            "args_digest": None,
            "session_taint": None,
            "decision": None,
            "outcome": None,
            "trace_id": None,
        }

    def _learn_agent(self, request: Message) -> None:
        meta = request.params.get("_meta")
        info = meta.get(CLIENT_INFO) if isinstance(meta, dict) else None
        if info is None and request.method == "initialize":  # older clients announce themselves once
            info = request.params.get("clientInfo")
        if name := _client_name(info):
            self.agent = name

    # --- hooks ----------------------------------------------------------------

    async def on_request(self, request: Message, upstream: Upstream) -> Decision:
        self._learn_agent(request)
        decision = await self.inner.on_request(request, upstream)
        if request.method != "tools/call":
            return decision

        params = decision.body.get("params", {}) if isinstance(decision, Replace) else request.params
        tool = params.get("name") if isinstance(params.get("name"), str) else None
        args = params.get("arguments")
        fields = self._fields("request", tool)
        fields["args_digest"] = self.digester.digest(args) if args is not None else None
        blocked = isinstance(decision, Block)
        control = reason = None
        if isinstance(decision, Block | Replace):
            control, reason = decision.control or None, decision.reason or None
        fields["decision"] = {"effect": "deny" if blocked else "allow", "control": control, "reason": reason}
        try:
            entry = await self.store.append(
                fields, args=args if self.keep_args and args is not None else None
            )
        except Exception as e:  # any failure to record means we don't forward
            log.error("could not write call %r to the ledger, so it was not forwarded: %s", tool, e)
            return Block(
                tool_error_result(
                    request,
                    "Blocked by Ledgerline: this call could not be recorded in the ledger,"
                    " so it was not run.",
                ),
                reason=f"ledger unavailable: {type(e).__name__}",
                control=CONTROL_LEDGER,
            )
        self.on_entry(entry)
        if not blocked and request.id is not None:
            self._pending[request.id] = (str(entry["entry_hash"]), tool)
        return decision

    async def on_response(self, request: Message, response: Message) -> Decision:
        decision = await self.inner.on_response(request, response)
        pending = self._pending.pop(request.id, None) if request.id is not None else None
        if request.method != "tools/call" or pending is None:
            return decision

        request_hash, tool = pending
        final: JSON = (
            decision.body
            if isinstance(decision, Replace)
            else decision.response
            if isinstance(decision, Block)
            else response.body
        )
        result: Any = final.get("result")
        error: Any = final.get("error")
        status = (
            "error"
            if error is not None
            else "tool_error"
            if isinstance(result, dict) and result.get("isError")
            else "ok"
        )
        fields = self._fields("outcome", tool)
        fields["outcome"] = {
            "status": status,
            "result_digest": self.digester.digest(error if error is not None else result),
            "request_hash": request_hash,
        }
        try:
            entry = await self.store.append(fields)
        except Exception as e:
            log.error("the call to %r ran, but its outcome could not be written to the ledger: %s", tool, e)
        else:
            self.on_entry(entry)
        return decision

    def observe(self, direction: Direction, message: Message) -> None:
        self.inner.observe(direction, message)
