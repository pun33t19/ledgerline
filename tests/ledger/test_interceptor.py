"""Write-before-forward: what the ledger records for allowed, blocked and failed calls."""

from typing import Any

import pytest

from ledgerline.jsonrpc import JSON, Message, encode, parse
from ledgerline.ledger.digest import Digester
from ledgerline.ledger.interceptor import LedgerInterceptor
from ledgerline.ledger.store import MemoryStore
from ledgerline.ledger.verify import verify_chain
from ledgerline.proxy.interceptor import FORWARD, Block, Decision, Forward, Interceptor, Upstream

pytestmark = pytest.mark.anyio

KEY = Digester(b"k" * 32)
ENVELOPE = {"io.modelcontextprotocol/clientInfo": {"name": "test-host", "version": "1.0"}}


def msg(body: JSON) -> Message:
    return parse(encode(body).rstrip(b"\n"))


def call(id_: int = 7, args: JSON | None = None) -> Message:
    params: JSON = {"name": "get_fact", "arguments": args or {}, "_meta": ENVELOPE}
    return msg({"jsonrpc": "2.0", "id": id_, "method": "tools/call", "params": params})


def reply(id_: int = 7, *, is_error: bool = False) -> Message:
    return msg({"jsonrpc": "2.0", "id": id_, "result": {"content": [], "isError": is_error}})


class Gate(Interceptor):
    """An inner chain that blocks or forwards, recording when it was consulted."""

    def __init__(self, block: bool = False) -> None:
        self.block = block

    async def on_request(self, request: Message, upstream: Upstream) -> Decision:
        if self.block and request.method == "tools/call":
            return Block(
                {"jsonrpc": "2.0", "id": request.id, "result": {}}, "tool_changed", "verify-before-call"
            )
        return FORWARD


class NoUpstream:
    async def request(self, method: str, params: JSON, *, like: Message) -> JSON:
        raise AssertionError("not used")


def ledger(inner: Interceptor, store: Any, **kw: Any) -> LedgerInterceptor:
    return LedgerInterceptor(
        inner,
        store,
        run_id="run-1",
        server="demo",
        digester=KEY,
        user="alice",
        tool_hash=lambda name: "a" * 64 if name == "get_fact" else None,
        **kw,
    )


async def test_allowed_call_is_written_before_forwarding_then_its_outcome() -> None:
    store = MemoryStore()
    seen: list[JSON] = []
    li = ledger(Gate(), store, on_entry=seen.append)

    decision = await li.on_request(call(args={"q": "x"}), NoUpstream())
    assert isinstance(decision, Forward)
    entries = await store.entries("run-1")
    assert len(entries) == 1, "the request entry exists by the time the call may be forwarded"
    request = entries[0]
    assert request["kind"] == "request"
    assert request["decision"] == {"effect": "allow", "control": None, "reason": None}
    assert request["actor"] == {
        "user": "alice",
        "agent": "test-host 1.0",
        "on_behalf_of_chain": ["alice", "test-host 1.0"],
    }
    assert request["tool_def_sha256"] == "a" * 64
    assert request["args_digest"] == KEY.digest({"q": "x"})

    await li.on_response(call(), reply(is_error=True))
    entries = await store.entries("run-1")
    outcome = entries[1]
    assert outcome["kind"] == "outcome"
    assert outcome["outcome"]["status"] == "tool_error"
    assert outcome["outcome"]["request_hash"] == request["entry_hash"]
    assert verify_chain(entries).ok
    assert seen == entries


async def test_blocked_call_is_recorded_as_denied_with_its_control() -> None:
    store = MemoryStore()
    li = ledger(Gate(block=True), store)
    decision = await li.on_request(call(), NoUpstream())
    assert isinstance(decision, Block)
    [entry] = await store.entries("run-1")
    assert entry["decision"] == {"effect": "deny", "control": "verify-before-call", "reason": "tool_changed"}


class CrashAfterCommit(MemoryStore):
    """Writes the entry, then fails, like a connection lost right after COMMIT."""

    async def append(self, fields: JSON, *, args: Any = None) -> JSON:
        await super().append(fields, args=args)
        raise ConnectionError("connection lost after commit")


class Down(MemoryStore):
    async def append(self, fields: JSON, *, args: Any = None) -> JSON:
        raise ConnectionError("database down")


@pytest.mark.parametrize("store_class", [Down, CrashAfterCommit])
async def test_fails_closed_when_the_entry_cant_be_confirmed(store_class: type[MemoryStore]) -> None:
    store = store_class()
    li = ledger(Gate(), store)
    decision = await li.on_request(call(), NoUpstream())
    assert isinstance(decision, Block), "an unrecorded call must not run"
    assert decision.control == "ledger"
    assert decision.response["result"]["isError"] is True
    # After a crash after commit the entry exists, but the call never ran: the ledger may
    # over-report an attempt, never under-report one.
    assert len(await store.entries("run-1")) == (1 if store_class is CrashAfterCommit else 0)


async def test_other_methods_are_not_recorded_and_raw_args_only_on_request() -> None:
    store = MemoryStore()
    li = ledger(Gate(), store, keep_args=True)
    await li.on_request(msg({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}), NoUpstream())
    assert await store.entries("run-1") == []
    await li.on_request(call(args={"secret": "s"}), NoUpstream())
    assert store.args == {("run-1", 1): {"secret": "s"}}
