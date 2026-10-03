"""An honest demo MCP server with a single ``get_weather`` tool backed by canned data.

It is the baseline that the Ledgerline proxy must relay without changing anything.

    demo-weather                          # stdio
    demo-weather --http :8081             # Streamable HTTP, stateless (protocol 2026-07-28)
    demo-weather --http :8081 --stateful  # legacy sessions (protocol 2025-11-25)
"""

from __future__ import annotations

import argparse
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from ledgerline.demo.common import Transport, serve

# Canned data keeps the server deterministic and offline, so test fixtures
# never change between runs. Values are (temperature °F, conditions).
READINGS: dict[str, tuple[float, str]] = {
    "san francisco, ca": (61, "Fog"),
    "new york, ny": (72, "Partly cloudy"),
    "pune, in": (84, "Humid, light rain"),
}


def get_weather(
    location: Annotated[str, Field(description="The city and state, e.g. San Francisco, CA")],
    unit: Annotated[str, Field(description="celsius or fahrenheit")] = "fahrenheit",
) -> str:
    """Look up canned weather. Raising ToolError makes the SDK return an isError result."""
    reading = READINGS.get(location.strip().lower())
    if reading is None:
        raise ToolError(
            f"No weather data for {location!r}. Try San Francisco, CA; New York, NY; or Pune, IN."
        )

    temp_f, conditions = reading
    match unit.lower():
        case "fahrenheit":
            temp, symbol = temp_f, "°F"
        case "celsius":
            temp, symbol = (temp_f - 32) * 5 / 9, "°C"
        case _:
            raise ToolError(f"Unknown unit {unit!r}; use celsius or fahrenheit.")

    return f"Current weather in {location}:\nTemperature: {temp:.0f}{symbol}\nConditions: {conditions}"


def build_server() -> MCPServer:
    server = MCPServer("weather", version="0.1.0")
    server.add_tool(
        get_weather,
        description="Get the current weather in a given location",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    return server


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    Transport.add_arguments(parser)
    # Accepted so every demo server takes the same flags; an honest server never exfiltrates anything.
    parser.add_argument("--exfil-log", help=argparse.SUPPRESS)
    serve(build_server(), Transport.from_args(parser.parse_args()))


if __name__ == "__main__":
    main()
