import io
import json

import pytest
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

from ledgerline.wiretap import Wiretap
from tests.conftest import BIN

pytestmark = pytest.mark.anyio


async def test_records_both_directions() -> None:
    out = io.StringIO()
    transport = Wiretap(stdio_client(StdioServerParameters(command=str(BIN / "demo-weather"))), out)
    async with Client(transport, cache=None) as client:
        await client.call_tool("get_weather", {"location": "Pune, IN"})

    records = [json.loads(line) for line in out.getvalue().splitlines()]
    assert {r["dir"] for r in records} == {"sent", "received"}
    assert all(r["msg"]["jsonrpc"] == "2.0" for r in records)

    calls = [r for r in records if r["msg"].get("method") == "tools/call"]
    assert len(calls) == 1
    assert calls[0]["dir"] == "sent"
    assert calls[0]["msg"]["params"]["arguments"] == {"location": "Pune, IN"}

    # Every request the client sent got exactly one response with the same id.
    sent_ids = [r["msg"]["id"] for r in records if r["dir"] == "sent" and "id" in r["msg"]]
    received_ids = [r["msg"]["id"] for r in records if r["dir"] == "received" and "id" in r["msg"]]
    assert sorted(sent_ids) == sorted(received_ids)
