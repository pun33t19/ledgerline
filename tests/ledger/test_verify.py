"""The verifier finds the first entry that can't be trusted, whatever was changed."""

import copy
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from ledgerline.ledger.hashing import GENESIS, seal
from ledgerline.ledger.verify import verify_chain


def chain(n: int) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for i in range(n):
        prev = entries[-1]["entry_hash"] if entries else GENESIS
        fields = {
            "run_id": "run-1",
            "kind": "request",
            "tool": f"tool_{i}",
            "decision": {"effect": "allow", "control": None, "reason": None},
            "outcome": None,
        }
        entries.append(seal(fields, seq=i + 1, prev_hash=prev))
    return entries


def test_empty_and_intact_chains() -> None:
    assert verify_chain([]).ok
    result = verify_chain(chain(5))
    assert result.ok
    assert result.verified == 5


def test_deleting_an_entry_breaks_the_chain_at_the_gap() -> None:
    entries = chain(5)
    del entries[2]
    result = verify_chain(entries)
    assert result.problem is not None
    assert (result.problem.index, result.problem.kind) == (2, "bad_seq")
    assert result.verified == 2


def test_rehashing_an_edit_moves_the_break_to_the_next_link() -> None:
    entries = chain(4)
    entries[1] = seal({**entries[1], "tool": "other"}, seq=2, prev_hash=entries[0]["entry_hash"])
    result = verify_chain(entries)
    assert result.problem is not None
    assert (result.problem.index, result.problem.kind) == (2, "broken_link")


def test_outcome_must_answer_an_earlier_request() -> None:
    entries = chain(1)
    outcome = {"run_id": "run-1", "kind": "outcome", "outcome": {"request_hash": "f" * 64}}
    entries.append(seal(outcome, seq=2, prev_hash=entries[0]["entry_hash"]))
    result = verify_chain(entries)
    assert result.problem is not None
    assert result.problem.kind == "dangling_reference"


def _string_paths(value: Any, path: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    if isinstance(value, dict):
        return [p for k, v in value.items() for p in _string_paths(v, (*path, k))]
    if isinstance(value, list):
        return [p for i, v in enumerate(value) for p in _string_paths(v, (*path, i))]
    return [path] if isinstance(value, str) and value else []


@settings(max_examples=300, deadline=None)
@given(n=st.integers(1, 8), data=st.data())
def test_any_single_character_edit_is_caught_at_that_entry(n: int, data: st.DataObject) -> None:
    entries = chain(n)
    target = data.draw(st.integers(0, n - 1), label="entry")
    paths = _string_paths(entries[target])
    path = data.draw(st.sampled_from(paths), label="field")
    parent: Any = entries[target]
    for key in path[:-1]:
        parent = parent[key]
    old = parent[path[-1]]
    pos = data.draw(st.integers(0, len(old) - 1), label="position")
    new_char = data.draw(st.characters(codec="utf-8").filter(lambda c: c != old[pos]), label="char")
    edited = copy.deepcopy(entries)
    holder: Any = edited[target]
    for key in path[:-1]:
        holder = holder[key]
    holder[path[-1]] = old[:pos] + new_char + old[pos + 1 :]

    result = verify_chain(edited)
    assert not result.ok
    assert result.problem is not None
    assert result.problem.index == target
    assert result.verified == target
