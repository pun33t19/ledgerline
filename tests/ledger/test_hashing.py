"""The hashing rule, checked against vectors computed outside this code."""

import copy
import json
from pathlib import Path
from typing import Any

from ledgerline.ledger.hashing import GENESIS, entry_hash, seal
from ledgerline.ledger.schema import Entry, json_schema
from ledgerline.ledger.verify import verify_chain

ROOT = Path(__file__).parent.parent.parent
VECTORS = ROOT / "spec" / "vectors"


def load(name: str) -> Any:
    return json.loads((VECTORS / name).read_text(encoding="utf-8"))


def test_reproduces_the_deep_dive_example() -> None:
    vector = load("deep-dive-entry-41.json")
    entry = vector["entry"]
    assert entry["prev_hash"] == GENESIS
    assert entry_hash(entry) == entry["entry_hash"]
    tampered = copy.deepcopy(entry)
    tampered["decision"]["effect"] = "deny"
    assert entry_hash(tampered) == vector["tampered"]["expected_entry_hash"]


def test_golden_chain_still_verifies() -> None:
    vector = load("chain-001.json")
    result = verify_chain(vector["entries"])
    assert result.ok
    assert result.count == vector["expected"]["count"]
    assert result.head_hash == vector["expected"]["head_hash"]
    for entry in vector["entries"]:
        Entry.model_validate(entry)  # the vector is valid v0.1


def test_golden_tamper_cases() -> None:
    for case in load("chain-001.json")["tampered"]:
        result = verify_chain(case["entries"])
        assert not result.ok, case["name"]
        assert result.problem is not None
        assert (result.problem.index, result.problem.kind) == (
            case["expected"]["index"],
            case["expected"]["kind"],
        ), case["name"]


def test_seal_links_and_hashes() -> None:
    first = seal({"run_id": "r", "x": 1}, seq=1, prev_hash=GENESIS)
    second = seal({"run_id": "r", "x": 2}, seq=2, prev_hash=first["entry_hash"])
    assert second["prev_hash"] == first["entry_hash"]
    assert entry_hash(second) == second["entry_hash"]
    assert seal({"x": 1, "run_id": "r"}, seq=1, prev_hash=GENESIS) == first  # key order doesn't matter


def test_event_schema_file_is_current() -> None:
    on_disk = (ROOT / "schema" / "event.schema.json").read_text(encoding="utf-8")
    assert on_disk == json_schema(), "schema/event.schema.json is stale: run `make event-schema`"
