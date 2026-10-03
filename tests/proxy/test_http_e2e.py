"""End to end over HTTP: demo-client → ledgerline proxy http → demo server (all real processes)."""

import io
import subprocess
from pathlib import Path

import httpx
import pytest
from mcp_types.jsonrpc import HEADER_MISMATCH

from ledgerline.demo.client import Options, run
from ledgerline.jsonrpc import parse
from ledgerline.proxy.http import check_routing_headers
from tests.conftest import BIN, Spawn

pytestmark = pytest.mark.anyio

MODERN_META = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientCapabilities": {},
}


def pin_http(lock: Path, url: str) -> None:
    subprocess.run(
        [str(BIN / "ledgerline"), "pin", "--yes", "--lock", str(lock), "--http", url],
        check=True,
        capture_output=True,
    )


@pytest.mark.parametrize(
    ("server_args", "legacy"),
    [
        pytest.param([], False, id="stateless"),
        pytest.param(["--stateful"], False, id="stateful"),
        pytest.param(["--stateful"], True, id="stateful-legacy"),
    ],
)
async def test_rug_pull_is_blocked_over_http(
    http_server: Spawn, spawn: Spawn, tmp_path: Path, server_args: list[str], legacy: bool
) -> None:
    lock = tmp_path / "ledgerline.lock"
    pin_http(lock, http_server("demo-rugpull", "--after", "99", *server_args))  # pin a fresh copy
    upstream = http_server("demo-rugpull", "--after", "3", *server_args)
    proxy = spawn(
        "ledgerline", "proxy", "http", "--upstream", upstream, "--listen", "{addr}", "--lock", str(lock)
    )
    out = io.StringIO()

    await run(Options(http=proxy, call="get_fact_of_the_day", repeat=4, legacy=legacy), out)

    text = out.getvalue()
    assert "Call 3 → Bananas are berries; strawberries are not." in text
    assert "Call 4 → Blocked by Ledgerline" in text
    assert "<IMPORTANT>" not in text


async def test_mismatched_routing_header_is_rejected(
    http_server: Spawn, spawn: Spawn, tmp_path: Path
) -> None:
    lock = tmp_path / "ledgerline.lock"
    upstream = http_server("demo-weather")
    pin_http(lock, upstream)
    proxy = spawn(
        "ledgerline", "proxy", "http", "--upstream", upstream, "--listen", "{addr}", "--lock", str(lock)
    )
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "get_weather", "arguments": {"location": "Pune, IN"}, "_meta": MODERN_META},
    }
    headers = {
        "mcp-protocol-version": "2026-07-28",
        "mcp-method": "tools/call",
        "mcp-name": "some_other_tool",  # a gateway routing on this would disagree with the body
        "accept": "application/json, text/event-stream",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(proxy, json=body, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == HEADER_MISMATCH


def request(body: dict[str, object]) -> object:
    import json

    return parse(json.dumps({"jsonrpc": "2.0", "id": 1, **body}).encode())


CALL = {"method": "tools/call", "params": {"name": "get_weather"}}


@pytest.mark.parametrize(
    ("headers", "problem"),
    [
        pytest.param(
            {"mcp-protocol-version": "2026-07-28", "mcp-method": "tools/call", "mcp-name": "get_weather"},
            None,
            id="ok",
        ),
        pytest.param({"mcp-protocol-version": "2025-11-25"}, None, id="legacy-without-headers"),
        pytest.param(
            {"mcp-protocol-version": "2026-07-28"},
            "Mcp-Method header is required",
            id="modern-missing-method",
        ),
        pytest.param(
            {"mcp-protocol-version": "2026-07-28", "mcp-method": "tools/call"},
            "Mcp-Name header is required",
            id="missing-name",
        ),
        pytest.param({"mcp-method": "tools/list"}, "does not match the body's method", id="method-mismatch"),
        pytest.param(
            {"mcp-method": "tools/call", "mcp-name": "other"},
            "does not match the body's 'name'",
            id="name-mismatch",
        ),
        pytest.param(
            {"mcp-method": "tools/call", "mcp-name": "=?base64?Z2V0X3dlYXRoZXI=?="},
            None,
            id="base64-encoded-name",
        ),
    ],
)
def test_check_routing_headers(headers: dict[str, str], problem: str | None) -> None:
    result = check_routing_headers(headers, request(CALL))  # type: ignore[arg-type]
    if problem is None:
        assert result is None
    else:
        assert result is not None
        assert problem in result


async def test_proxy_rejects_dns_rebinding_and_browser_origins(
    http_server: Spawn, spawn: Spawn, tmp_path: Path
) -> None:
    lock = tmp_path / "ledgerline.lock"
    upstream = http_server("demo-weather")
    pin_http(lock, upstream)
    proxy = spawn(
        "ledgerline", "proxy", "http", "--upstream", upstream, "--listen", "{addr}", "--lock", str(lock)
    )
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"_meta": MODERN_META}}
    base = {
        "mcp-protocol-version": "2026-07-28",
        "mcp-method": "tools/list",
        "accept": "application/json, text/event-stream",
    }

    async with httpx.AsyncClient() as client:
        rebound = await client.post(proxy, json=body, headers={**base, "Host": "attacker.example:9000"})
        from_page = await client.post(
            proxy, json=body, headers={**base, "Origin": "https://attacker.example"}
        )
        normal = await client.post(proxy, json=body, headers=base)

    assert rebound.status_code == 403
    assert from_page.status_code == 403
    assert normal.status_code == 200
