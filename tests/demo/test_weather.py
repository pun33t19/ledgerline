import pytest
from mcp import Client
from mcp.types import TextContent

from ledgerline.demo.servers.weather import build_server

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ("args", "want_text", "want_error"),
    [
        pytest.param({"location": "New York, NY"}, "Temperature: 72°F", False, id="fahrenheit-default"),
        pytest.param({"location": "Pune, IN", "unit": "celsius"}, "Temperature: 29°C", False, id="celsius"),
        pytest.param({"location": "  san FRANCISCO, ca "}, "Conditions: Fog", False, id="case-insensitive"),
        pytest.param({"location": "Atlantis"}, "No weather data", True, id="unknown-location"),
        pytest.param({"location": "Pune, IN", "unit": "kelvin"}, "Unknown unit", True, id="bad-unit"),
    ],
)
async def test_get_weather(args: dict[str, str], want_text: str, want_error: bool) -> None:
    async with Client(build_server(), cache=None) as client:
        result = await client.call_tool("get_weather", args)
    assert isinstance(result.content[0], TextContent)
    assert want_text in result.content[0].text
    assert result.is_error is want_error


async def test_tool_definition() -> None:
    async with Client(build_server(), cache=None) as client:
        (tool,) = (await client.list_tools()).tools
    assert tool.name == "get_weather"
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is True
    assert tool.input_schema["required"] == ["location"]
    assert "<IMPORTANT>" not in (tool.description or ""), (
        "the honest server must not carry hidden instructions"
    )
