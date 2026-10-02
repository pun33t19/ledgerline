"""End-to-end tests: demo-client against real demo-server processes."""

import io
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from ledgerline.demo.client import Options, parse_args, run
from tests.conftest import BIN

pytestmark = pytest.mark.anyio

StartServer = Callable[..., str]


def sent_methods(wire: Path) -> list[str]:
    records = [json.loads(line) for line in wire.read_text().splitlines()]
    return [r["msg"]["method"] for r in records if r["dir"] == "sent" and "method" in r["msg"]]


@pytest.mark.parametrize(
    ("server_args", "legacy", "protocol", "handshake"),
    [
        pytest.param([], False, "2026-07-28", ["server/discover", "tools/list"], id="stateless"),
        pytest.param(["--stateful"], False, "2026-07-28", ["server/discover", "tools/list"], id="stateful"),
        pytest.param(
            ["--stateful"],
            True,
            "2025-11-25",
            ["initialize", "notifications/initialized", "tools/list"],
            id="stateful-legacy",
        ),
    ],
)
async def test_rug_pull_over_http(
    http_server: StartServer,
    tmp_path: Path,
    server_args: list[str],
    legacy: bool,
    protocol: str,
    handshake: list[str],
) -> None:
    url = http_server("demo-rugpull", "--after", "2", *server_args)
    wire = tmp_path / "wire.jsonl"
    out = io.StringIO()

    await run(Options(http=url, wire=wire, call="get_fact_of_the_day", repeat=3, legacy=legacy), out)

    text = out.getvalue()
    assert f"(protocol {protocol})" in text
    assert "Call 3 → Bananas are berries; strawberries are not." in text
    assert '⚠ Tool "get_fact_of_the_day" changed after call 2' in text
    assert text.count("⚠") == 1, "the change must be reported exactly once"
    assert sent_methods(wire)[: len(handshake)] == handshake


async def test_stdio(tmp_path: Path) -> None:
    out = io.StringIO()
    opts = Options(
        call="get_weather",
        args='{"location": "Pune, IN", "unit": "celsius"}',
        command=[str(BIN / "demo-weather")],
    )
    await run(opts, out)
    assert "Connected to weather 0.1.0 (protocol 2026-07-28)" in out.getvalue()
    assert "Call 1 → Current weather in Pune, IN: | Temperature: 29°C" in out.getvalue()


@pytest.mark.parametrize(
    ("opts", "message"),
    [
        pytest.param(Options(), "give a server command", id="no-target"),
        pytest.param(Options(http="http://x", command=["x"]), "not both", id="both-targets"),
        pytest.param(Options(http="http://x", args="[1]"), "JSON object", id="args-not-object"),
    ],
)
async def test_rejects_bad_options(opts: Options, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        await run(opts, io.StringIO())


def test_parse_args_splits_server_command() -> None:
    opts = parse_args(["--call", "add", "--repeat", "2", "--", "demo-rugpull", "--after", "1"])
    assert opts.call == "add"
    assert opts.repeat == 2
    assert opts.command == ["demo-rugpull", "--after", "1"]
