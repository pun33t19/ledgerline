"""A minimal MCP client for exercising the demo servers.

It runs discover/initialize → tools/list → tools/call, optionally recording
raw JSON-RPC traffic. After every call it re-lists the tools and reports any
definition that changed, which is how you see a rug pull happen.

    demo-client [options] -- <server command> [args...]   # stdio
    demo-client [options] --http http://localhost:8081/mcp
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

import anyio
from mcp import Client, StdioServerParameters
from mcp.client._transport import Transport
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, Implementation, TextContent, Tool

from ledgerline.wiretap import Wiretap

# Fixed rather than ledgerline.__version__: it is sent on the wire, so tying it
# to the package version would change the golden fixtures on every release.
CLIENT_INFO = Implementation(name="ledgerline-demo-client", version="0.1.0")


@dataclass
class Options:
    http: str | None = None
    wire: Path | None = None
    call: str | None = None
    args: str = "{}"
    repeat: int = 1
    legacy: bool = False
    command: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ToolInfo:
    tool: Tool
    # A preview of Phase 2 pinning: SHA-256 of the tool's JSON with sorted keys.
    # Phase 2 switches to RFC 8785 canonical JSON, which also pins number formatting.
    sha256: str


def fingerprint(tool: Tool) -> str:
    data = json.dumps(
        tool.model_dump(by_alias=True, mode="json", exclude_none=True),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(data.encode()).hexdigest()


def make_transport(opts: Options) -> Transport:
    if opts.http and opts.command:
        raise ValueError("use either --http or a server command, not both")
    if opts.http:
        return streamable_http_client(opts.http)
    if opts.command:
        return stdio_client(StdioServerParameters(command=opts.command[0], args=opts.command[1:]))
    raise ValueError("give a server command after -- or use --http (see --help)")


async def list_tools(client: Client) -> dict[str, ToolInfo]:
    tools: dict[str, ToolInfo] = {}
    cursor: str | None = None
    while True:  # follow pagination until the server says there are no more pages
        page = await client.list_tools(cursor=cursor)
        for tool in page.tools:
            tools[tool.name] = ToolInfo(tool, fingerprint(tool))
        cursor = page.next_cursor
        if cursor is None:
            return tools


def print_tool(out: TextIO, info: ToolInfo) -> None:
    print(f"- {info.tool.name}  [sha256 {info.sha256[:12]}]", file=out)
    for line in (info.tool.description or "").split("\n"):
        print(f"    │ {line}", file=out)


def result_text(result: CallToolResult) -> str:
    text = " ".join(c.text for c in result.content if isinstance(c, TextContent))
    return text.replace("\n", " | ") + ("  (isError)" if result.is_error else "")


async def run(opts: Options, out: TextIO) -> None:
    call_args: Any = json.loads(opts.args)
    if not isinstance(call_args, dict):
        raise ValueError("--args must be a JSON object")
    transport = make_transport(opts)

    with ExitStack() as files:
        if opts.wire:
            transport = Wiretap(transport, files.enter_context(opts.wire.open("w", encoding="utf-8")))

        # cache=None: the SDK caches tools/list responses for as long as the server's
        # ttlMs hint says. The demo servers send ttlMs=0, but a malicious server could
        # send a long TTL and keep clients on a stale menu, so always refetch.
        client = Client(
            transport,
            cache=None,
            # "auto" tries the 2026-07-28 server/discover first; "legacy" forces the
            # older initialize handshake.
            mode="legacy" if opts.legacy else "auto",
            client_info=CLIENT_INFO,
        )
        async with client:
            if info := client.server_info:
                print(
                    f"Connected to {info.name} {info.version} (protocol {client.protocol_version})", file=out
                )

            pinned = await list_tools(client)
            print("\nTools:", file=out)
            for name in sorted(pinned):
                print_tool(out, pinned[name])

            if opts.call is None:
                return
            for i in range(1, opts.repeat + 1):
                result = await client.call_tool(opts.call, call_args)
                print(f"\nCall {i} → {result_text(result)}", file=out)

                current = await list_tools(client)
                for name in sorted(current):
                    old = pinned.get(name)
                    if old and old.sha256 != current[name].sha256:
                        print(
                            f'\n⚠ Tool "{name}" changed after call {i} '
                            f"(sha256 {old.sha256[:12]} → {current[name].sha256[:12]}). New definition:",
                            file=out,
                        )
                        print_tool(out, current[name])
                pinned = current


def parse_args(argv: list[str]) -> Options:
    # Everything after "--" is the server command, passed through untouched.
    if "--" in argv:
        split = argv.index("--")
        argv, command = argv[:split], argv[split + 1 :]
    else:
        command = []

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--http", metavar="URL", help="connect to a Streamable HTTP server instead of a command"
    )
    parser.add_argument("--wire", type=Path, help="record raw JSON-RPC traffic to this JSONL file")
    parser.add_argument("--call", metavar="TOOL", help="tool to call (omit to only list tools)")
    parser.add_argument("--args", default="{}", help="tool arguments as a JSON object")
    parser.add_argument("--repeat", type=int, default=1, help="number of times to call the tool")
    parser.add_argument("--legacy", action="store_true", help="use the pre-2026 initialize handshake")
    ns = parser.parse_args(argv)
    return Options(
        http=ns.http,
        wire=ns.wire,
        call=ns.call,
        args=ns.args,
        repeat=ns.repeat,
        legacy=ns.legacy,
        command=command,
    )


def main() -> None:
    try:
        anyio.run(run, parse_args(sys.argv[1:]), sys.stdout)
    except (ValueError, OSError) as e:
        sys.exit(f"demo-client: {e}")


if __name__ == "__main__":
    main()
