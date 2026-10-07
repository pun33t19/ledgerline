"""Sealing entries into a hash chain (ADR-007).

``entry_hash = SHA-256( RFC 8785 canonical JSON of the entry without entry_hash )``

Because ``prev_hash`` is inside the hashed bytes, each entry commits to the
one before it: changing any entry changes its hash, which no longer matches
the next entry's ``prev_hash``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ledgerline.pin.canonical import sha256_hex

GENESIS = "0" * 64  # prev_hash of the first entry in a chain


def entry_hash(entry: Mapping[str, Any]) -> str:
    """The hash an entry *should* have, recomputed from its contents."""
    return sha256_hex({k: v for k, v in entry.items() if k != "entry_hash"})


def seal(fields: Mapping[str, Any], *, seq: int, prev_hash: str) -> dict[str, Any]:
    """Place ``fields`` at ``seq`` after ``prev_hash`` and add its ``entry_hash``."""
    entry = {**fields, "seq": seq, "prev_hash": prev_hash}
    entry.pop("entry_hash", None)
    entry["entry_hash"] = entry_hash(entry)
    return entry
