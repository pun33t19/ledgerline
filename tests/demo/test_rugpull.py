import anyio
import pytest
from mcp import Client

from ledgerline.demo.common import FAKE_SECRETS_DISPLAY_PATH
from ledgerline.demo.servers.rugpull import BENIGN_DESCRIPTION, TOOL_NAME, build_server

pytestmark = pytest.mark.anyio


async def description(client: Client) -> str:
    (tool,) = (await client.list_tools()).tools
    return tool.description or ""


async def test_rug_pull_after_n_calls() -> None:
    after = 3
    async with Client(build_server(after), cache=None) as client:
        for i in range(1, after):
            await client.call_tool(TOOL_NAME, {})
            assert await description(client) == BENIGN_DESCRIPTION, f"changed early, after call {i}"

        # Only a client that subscribes hears the announcement.
        async with client.listen(tools_list_changed=True) as sub:
            await client.call_tool(TOOL_NAME, {})  # call number `after` triggers the pull
            with anyio.fail_after(5):
                await anext(aiter(sub))

        changed = await description(client)
    assert "<IMPORTANT>" in changed
    assert FAKE_SECRETS_DISPLAY_PATH in changed


async def test_rug_pull_happens_once() -> None:
    async with Client(build_server(after=1), cache=None) as client:
        await client.call_tool(TOOL_NAME, {})
        first = await description(client)
        for _ in range(5):
            await client.call_tool(TOOL_NAME, {})
        assert await description(client) == first


def test_after_must_be_positive() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        build_server(after=0)
