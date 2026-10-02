"""A plain JSON Lines log of everything the proxy sees, plus pin alerts.

Temporary: Phase 3 replaces this with the tamper-evident ledger. Unlike the
ledger, anyone can edit this file afterwards without detection.

Each line is one of::

    {"ts": "...", "dir": "client→server", "msg": {...}}
    {"ts": "...", "alert": {"event": "tool_changed", "tool": "...", ...}}
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, TextIO

from ledgerline.jsonrpc import JSON, Message
from ledgerline.proxy.interceptor import Direction, Interceptor


class JsonlLog(Interceptor):
    def __init__(self, out: TextIO) -> None:
        self.out = out

    def observe(self, direction: Direction, message: Message) -> None:
        self._write({"dir": direction, "msg": message.body})

    def alert(self, event: JSON) -> None:
        self._write({"alert": event})

    def _write(self, record: dict[str, Any]) -> None:
        line = {"ts": datetime.now(UTC).isoformat(timespec="milliseconds"), **record}
        self.out.write(json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n")
        self.out.flush()
