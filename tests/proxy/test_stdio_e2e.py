"""End to end over stdio: demo-client → ledgerline proxy stdio → demo server (all real processes)."""

import io
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from ledgerline.demo.client import Options, run
from ledgerline.jsonrpc import PARSE_ERROR, parse
from ledgerline.pin.lockfile import Lockfile
from ledgerline.proxy.interceptor import Chain
from ledgerline.proxy.stdio import Line, StdioProxy
from tests.conftest import BIN, FIXTURES

pytestmark = pytest.mark.anyio

LEDGERLINE = str(BIN / "ledgerline")


def pin(lock: Path, *server: str) -> None:
    subprocess.run(
        [LEDGERLINE, "pin", "--yes", "--lock", str(lock), "--", *server], check=True, capture_output=True
    )


def via_proxy(lock: Path, *server: str, extra: tuple[str, ...] = ()) -> list[str]:
    return [LEDGERLINE, "proxy", "stdio", "--lock", str(lock), *extra, "--", *server]


@pytest.mark.parametrize(
    ("fixture", "server", "opts"),
    [
        pytest.param(
            "weather-stdio.jsonl",
            "demo-weather",
            Options(call="get_weather", args='{"location":"Pune, IN","unit":"celsius"}'),
            id="weather",
        ),
        pytest.param(
            "weather-stdio-legacy.jsonl",
            "demo-weather",
            Options(call="get_weather", args='{"location":"Pune, IN","unit":"celsius"}', legacy=True),
            id="weather-legacy",
        ),
        pytest.param(
            "poisoned-stdio.jsonl",
            "demo-poisoned",
            Options(call="add", args='{"a":2,"b":3,"sidenote":"FAKE_API_KEY=demo-not-a-real-key"}'),
            id="poisoned",
        ),
    ],
)
async def test_proxy_is_transparent(tmp_path: Path, fixture: str, server: str, opts: Options) -> None:
    """Re-capturing a Phase 1 fixture through the proxy gives exactly the same conversation.

    The proxy's own verification requests are invisible to the client, and
    every message it forwards is byte-for-byte what the other side sent.
    """
    lock, wire = tmp_path / "ledgerline.lock", tmp_path / "wire.jsonl"
    pin(lock, str(BIN / server))
    opts.command, opts.wire = via_proxy(lock, str(BIN / server)), wire

    await run(opts, io.StringIO())

    assert wire.read_text() == (FIXTURES / fixture).read_text()


@pytest.mark.parametrize("no_relist", [False, True], ids=["host-relists", "host-never-relists"])
async def test_rug_pull_is_blocked(tmp_path: Path, no_relist: bool) -> None:
    lock = tmp_path / "ledgerline.lock"
    server = (str(BIN / "demo-rugpull"), "--after", "3")
    pin(lock, *server)
    out = io.StringIO()

    await run(
        Options(call="get_fact_of_the_day", repeat=4, no_relist=no_relist, command=via_proxy(lock, *server)),
        out,
    )

    text = out.getvalue()
    assert "Call 3 → Bananas are berries; strawberries are not." in text
    assert "Call 4 → Blocked by Ledgerline: tool 'get_fact_of_the_day' was not called" in text
    assert "(isError)" in text
    if not no_relist:
        assert '⚠ Tool "get_fact_of_the_day" is no longer listed (after call 3).' in text
        assert "<IMPORTANT>" not in text, "the changed description must never reach the client"


async def test_without_per_call_verification_a_silent_rug_pull_succeeds(tmp_path: Path) -> None:
    """Why --no-verify-each-call is not the default: a host that never re-lists isn't protected."""
    lock = tmp_path / "ledgerline.lock"
    server = (str(BIN / "demo-rugpull"), "--after", "3")
    pin(lock, *server)
    out = io.StringIO()
    command = via_proxy(lock, *server, extra=("--no-verify-each-call",))

    await run(Options(call="get_fact_of_the_day", repeat=4, no_relist=True, command=command), out)

    assert "Call 4 → Honey never spoils." in out.getvalue()


async def test_garbage_from_client_is_answered_not_forwarded(tmp_path: Path) -> None:
    lock = tmp_path / "ledgerline.lock"
    pin(lock, str(BIN / "demo-weather"))
    discover = (FIXTURES / "weather-stdio.jsonl").read_text().splitlines()[0]
    discover_body = discover[discover.index('"msg":') + 6 : -1].encode()

    async def lines() -> AsyncIterator[Line]:
        yield b"this is not json\n"
        yield discover_body + b"\n"

    replies: list[bytes] = []

    async def collect(data: bytes) -> None:
        replies.append(data)

    proxy = StdioProxy([str(BIN / "demo-weather")], Chain([]))
    await proxy.run(lines(), collect)

    first, second = (parse(r.rstrip(b"\n")) for r in replies)
    assert first.body["error"]["code"] == PARSE_ERROR
    assert first.id is None
    assert second.id == 1
    assert second.result is not None


def test_missing_lockfile_refuses_to_start(tmp_path: Path) -> None:
    result = subprocess.run(
        via_proxy(tmp_path / "missing.lock", str(BIN / "demo-weather")),
        input=b"",
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert b"run `ledgerline pin` first" in result.stderr


async def test_tofu_creates_the_lockfile(tmp_path: Path) -> None:
    lock = tmp_path / "new.lock"
    command = via_proxy(lock, str(BIN / "demo-weather"), extra=("--tofu",))

    await run(Options(command=command), io.StringIO())

    assert set(Lockfile.load(lock).tools) == {"get_weather"}
