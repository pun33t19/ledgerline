"""Check a chain of entries and point to the first one that can't be trusted.

Works on plain JSON (what the database, an export file or the browser holds),
not on parsed models, so it sees exactly the bytes that were sealed. For each
entry, in order:

1. it has the fields a chain needs;
2. ``seq`` is the next number (an entry was removed or reordered otherwise);
3. ``prev_hash`` equals the previous entry's ``entry_hash`` (the link holds);
4. recomputing ``entry_hash`` from its contents gives the stored value (it
   wasn't edited);
5. it belongs to the same run as the first entry;
6. an outcome's ``request_hash`` names an earlier entry.

The order matters: any single edit is reported at the entry that was edited.

Everything before the first problem is verified; nothing after it can be trusted.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel

from ledgerline.ledger.hashing import GENESIS, entry_hash
from ledgerline.pin.canonical import NotCanonicalizable

ProblemKind = Literal["malformed", "wrong_run", "bad_seq", "broken_link", "edited", "dangling_reference"]

_REQUIRED = ("seq", "run_id", "prev_hash", "entry_hash")


class Problem(BaseModel):
    index: int
    seq: int | None
    kind: ProblemKind
    message: str
    expected: str | None = None
    found: str | None = None


class VerifyResult(BaseModel):
    ok: bool
    count: int
    verified: int  # entries checked and found intact before the first problem
    head_hash: str | None  # entry_hash of the last verified entry
    problem: Problem | None = None


def _seq(entry: Mapping[str, Any]) -> int | None:
    seq = entry.get("seq")
    return seq if isinstance(seq, int) and not isinstance(seq, bool) else None


def verify_chain(entries: Sequence[Any]) -> VerifyResult:
    hashes: set[str] = set()
    prev = GENESIS
    run_id: object = None

    def fail(
        i: int, kind: ProblemKind, message: str, expected: str | None = None, found: object = None
    ) -> VerifyResult:
        entry = entries[i]
        return VerifyResult(
            ok=False,
            count=len(entries),
            verified=i,
            head_hash=None if i == 0 else str(entries[i - 1]["entry_hash"]),
            problem=Problem(
                index=i,
                seq=_seq(entry) if isinstance(entry, Mapping) else None,
                kind=kind,
                message=message,
                expected=expected,
                found=None if found is None else str(found),
            ),
        )

    for i, entry in enumerate(entries):
        n = i + 1
        if not isinstance(entry, Mapping) or any(k not in entry for k in _REQUIRED):
            return fail(i, "malformed", f"Entry {n} is missing fields every ledger entry has.")
        if _seq(entry) != n:
            return fail(
                i,
                "bad_seq",
                f"Entry {n} has sequence number {entry['seq']}: an entry was removed, added or reordered.",
                str(n),
                entry["seq"],
            )
        if entry["prev_hash"] != prev:
            return fail(
                i,
                "broken_link",
                f"Entry {n} doesn't point to the entry before it: the chain was cut or rewritten here.",
                prev,
                entry["prev_hash"],
            )
        try:
            recomputed = entry_hash(entry)
        except NotCanonicalizable:
            return fail(i, "malformed", f"Entry {n} contains a value that can't be canonicalised.")
        if recomputed != entry["entry_hash"]:
            return fail(
                i,
                "edited",
                f"Entry {n} was changed after it was written: its contents no longer match its hash.",
                str(entry["entry_hash"]),
                recomputed,
            )
        if i == 0:
            run_id = entry["run_id"]
        elif entry["run_id"] != run_id:
            return fail(
                i, "wrong_run", f"Entry {n} belongs to a different run.", str(run_id), entry["run_id"]
            )
        outcome = entry.get("outcome")
        if isinstance(outcome, Mapping) and outcome.get("request_hash") not in hashes:
            return fail(
                i,
                "dangling_reference",
                f"Entry {n} answers a request that isn't earlier in this chain.",
                None,
                outcome.get("request_hash"),
            )
        hashes.add(str(entry["entry_hash"]))
        prev = str(entry["entry_hash"])

    return VerifyResult(
        ok=True,
        count=len(entries),
        verified=len(entries),
        head_hash=prev if entries else None,
    )
