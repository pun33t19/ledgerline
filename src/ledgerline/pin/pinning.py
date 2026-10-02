"""``ledgerline pin``: fetch a server's tool definitions so a person can review and approve them."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, TextIO

from mcp import Client
from mcp.client._transport import Transport
from mcp.types import Implementation

from ledgerline import __version__
from ledgerline.pin.lockfile import Lockfile, PinnedTool
from ledgerline.wiretap import Direction, Wiretap

CLIENT_INFO = Implementation(name="ledgerline-pin", version=__version__)


@dataclass
class Snapshot:
    server: dict[str, Any]
    tools: dict[str, PinnedTool]


async def fetch_snapshot(transport: Transport) -> Snapshot:
    """Connect, list every tool (all pages) and return the definitions *exactly as the server sent them*.

    The SDK turns tools into Python objects, which can add or drop fields. The
    proxy fingerprints the raw JSON, so pinning must too: a Wiretap sink grabs
    the raw ``tools/list`` results off the wire.
    """
    list_ids: set[Any] = set()
    raw_tools: list[dict[str, Any]] = []

    def capture(direction: Direction, message: dict[str, Any]) -> None:
        if direction == "sent" and message.get("method") == "tools/list":
            list_ids.add(message.get("id"))
        elif direction == "received" and message.get("id") in list_ids:
            raw_tools.extend(t for t in (message.get("result") or {}).get("tools", []) if isinstance(t, dict))

    async with Client(Wiretap(transport, capture), cache=None, client_info=CLIENT_INFO) as client:
        cursor: str | None = None
        while True:
            page = await client.list_tools(cursor=cursor)
            cursor = page.next_cursor
            if cursor is None:
                break
        info = client.server_info
        server = {"name": info.name, "version": info.version} if info else {}

    tools = {t["name"]: PinnedTool.of(t) for t in raw_tools if isinstance(t.get("name"), str)}
    return Snapshot(server=server, tools=tools)


@dataclass
class Changes:
    added: list[str]
    changed: list[str]
    removed: list[str]
    unchanged: list[str]

    @property
    def any(self) -> bool:
        return bool(self.added or self.changed or self.removed)


def compare(old: Lockfile | None, new: Snapshot) -> Changes:
    old_tools = old.tools if old else {}
    return Changes(
        added=sorted(n for n in new.tools if n not in old_tools),
        changed=sorted(n for n in new.tools if n in old_tools and old_tools[n].sha256 != new.tools[n].sha256),
        removed=sorted(n for n in old_tools if n not in new.tools),
        unchanged=sorted(
            n for n in new.tools if n in old_tools and old_tools[n].sha256 == new.tools[n].sha256
        ),
    )


def print_review(out: TextIO, snapshot: Snapshot, changes: Changes) -> None:
    """Show every new or changed definition in full: review means reading all of it."""
    name = snapshot.server.get("name", "?")
    print(
        f"Server {name} {snapshot.server.get('version', '')} offers {len(snapshot.tools)} tool(s).", file=out
    )
    for label, names in (("NEW", changes.added), ("CHANGED", changes.changed)):
        for tool in names:
            pinned = snapshot.tools[tool]
            print(f"\n[{label}] {tool}  sha256 {pinned.sha256}", file=out)
            for line in json.dumps(pinned.definition, indent=2, ensure_ascii=False).splitlines():
                print(f"    {line}", file=out)
    for tool in changes.removed:
        print(f"\n[REMOVED] {tool} (no longer offered; its pin will be dropped)", file=out)
    if changes.unchanged:
        print(f"\nUnchanged: {', '.join(changes.unchanged)}", file=out)
