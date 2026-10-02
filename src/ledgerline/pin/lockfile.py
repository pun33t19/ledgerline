"""``ledgerline.lock``: the tool definitions a person has approved.

Each pinned tool stores its SHA-256 *and* its full definition, so a reviewer
can read exactly what was approved and see what changed when a pin fails.

Example::

    {
      "version": 1,
      "server": {"name": "daily-facts", "version": "1.0.0"},
      "tools": {
        "get_fact_of_the_day": {"sha256": "b45a…", "definition": {...}}
      }
    }

``server`` is informational only: servers report their own name, so it can't
be trusted for identity. One lock file pins one upstream server.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ledgerline.pin.canonical import sha256_hex

LOCKFILE_VERSION = 1
DEFAULT_LOCKFILE = Path("ledgerline.lock")


class LockfileError(ValueError):
    """The lock file is missing, unreadable or has the wrong shape."""


@dataclass(frozen=True)
class PinnedTool:
    sha256: str
    definition: dict[str, Any]

    @classmethod
    def of(cls, definition: dict[str, Any]) -> PinnedTool:
        return cls(sha256_hex(definition), definition)


@dataclass
class Lockfile:
    tools: dict[str, PinnedTool] = field(default_factory=dict)
    server: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Lockfile:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise LockfileError(f"{path} not found; run `ledgerline pin` first (or use --tofu)") from None
        except (OSError, ValueError) as e:
            raise LockfileError(f"cannot read {path}: {e}") from None

        if not isinstance(data, dict) or data.get("version") != LOCKFILE_VERSION:
            raise LockfileError(f"{path}: unsupported lock file (expected version {LOCKFILE_VERSION})")
        tools: dict[str, PinnedTool] = {}
        for name, entry in (data.get("tools") or {}).items():
            if not isinstance(entry, dict) or not isinstance(entry.get("definition"), dict):
                raise LockfileError(f"{path}: tool {name!r} has no definition")
            pinned = PinnedTool.of(entry["definition"])
            # Recompute rather than trust the stored hash, so a hand-edited
            # definition can't sit behind a stale hash.
            if entry.get("sha256") != pinned.sha256:
                raise LockfileError(f"{path}: tool {name!r} sha256 does not match its definition")
            tools[name] = pinned
        return cls(tools=tools, server=dict(data.get("server") or {}))

    def save(self, path: Path) -> None:
        data = {
            "version": LOCKFILE_VERSION,
            "server": self.server,
            "tools": {
                name: {"sha256": t.sha256, "definition": t.definition}
                for name, t in sorted(self.tools.items())
            },
        }
        text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        # Write to a temporary file and rename it into place, so a crash can
        # never leave a half-written lock file behind.
        fd, tmp = tempfile.mkstemp(dir=path.parent if str(path.parent) else ".", prefix=f".{path.name}.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            Path(tmp).replace(path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
