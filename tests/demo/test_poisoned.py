from pathlib import Path

import pytest
from mcp import Client
from mcp.types import TextContent

from ledgerline.demo.common import FAKE_SECRETS_DISPLAY_PATH, ExfilLog
from ledgerline.demo.servers.poisoned import build_server

pytestmark = pytest.mark.anyio


async def test_description_hides_instructions() -> None:
    async with Client(build_server(), cache=None) as client:
        (tool,) = (await client.list_tools()).tools
    desc = tool.description or ""
    assert desc.startswith("Adds two numbers."), "should open innocently"
    for hidden in ("<IMPORTANT>", FAKE_SECRETS_DISPLAY_PATH, "'sidenote'", "Do not mention"):
        assert hidden in desc


async def test_add_captures_sidenote(tmp_path: Path) -> None:
    log = tmp_path / "exfil.log"
    async with Client(build_server(exfil=ExfilLog(log)), cache=None) as client:
        result = await client.call_tool("add", {"a": 2, "b": 3})
        assert isinstance(result.content[0], TextContent)
        assert result.content[0].text == "5"
        assert not log.exists(), "no sidenote given, but something was exfiltrated"

        await client.call_tool("add", {"a": 1, "b": 1, "sidenote": "FAKE_API_KEY=x"})

    assert log.read_text() == "add\tFAKE_API_KEY=x\n"
    assert log.stat().st_mode & 0o777 == 0o600
