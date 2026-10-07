"""Every Lab scenario is a security regression test: both outcomes must match what it promises."""

import itertools
from typing import Any

import pytest

from ledgerline.ledger.verify import verify_chain
from ledgerline.sim.catalog import BY_ID, SCENARIOS
from ledgerline.sim.coverage import compute_coverage
from ledgerline.sim.events import (
    Controls,
    Decision,
    Exfiltration,
    LedgerEntry,
    MessageEvent,
    Outcome,
    Pinned,
    Step,
)
from ledgerline.sim.runner import Runner
from ledgerline.sim.scenario import Scenario

pytestmark = pytest.mark.anyio


async def run(scenario: Scenario, controls: Controls | None = None) -> list[Any]:
    events: list[Any] = []
    await Runner(scenario, controls or Controls(), events.append).run()
    return events


def outcome(events: list[Any], mode: str) -> Outcome:
    (found,) = [e for e in events if isinstance(e, Outcome) and e.mode == mode]
    return found


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.id for s in SCENARIOS])
async def test_outcomes_match_the_scenario(scenario: Scenario) -> None:
    events = await run(scenario)
    assert outcome(events, "unprotected").verdict == scenario.expected_unprotected
    assert outcome(events, "protected").verdict == scenario.expected_protected


@pytest.mark.parametrize(
    ("scenario_id", "switched_off", "control"),
    [
        ("rug-pull", "pinning", "tool-pinning"),
        ("silent-rug-pull", "verify_each_call", "verify-before-call"),
        ("new-unreviewed-tool", "pinning", "tool-pinning"),
        ("parser-differential", "strict_parsing", "strict-parsing"),
    ],
)
async def test_the_named_control_is_what_stops_it(scenario_id: str, switched_off: str, control: str) -> None:
    scenario = BY_ID[scenario_id]
    protected_on = outcome(await run(scenario), "protected")
    assert protected_on.verdict == "safe"
    assert control in protected_on.stopped_by

    protected_off = outcome(await run(scenario, Controls(**{switched_off: False})), "protected")
    assert protected_off.verdict == "harmed", f"without {switched_off} the attack should succeed"


async def test_event_stream_is_well_formed() -> None:
    events = await run(BY_ID["silent-rug-pull"])
    assert [e.seq for e in events] == list(range(1, len(events) + 1))
    assert all(a.t_ms <= b.t_ms for a, b in itertools.pairwise(events))
    assert isinstance(events[0], Pinned)

    protected = [e for e in events if isinstance(e, MessageEvent) and e.mode == "protected"]
    unprotected = [e for e in events if isinstance(e, MessageEvent) and e.mode == "unprotected"]
    assert {(e.source, e.target) for e in unprotected} == {("host", "server"), ("server", "host")}
    assert ("host", "ledgerline") in {(e.source, e.target) for e in protected}
    assert any(e.internal for e in protected), "the proxy's own check before the call is visible"

    (blocked,) = [e for e in events if isinstance(e, Decision)]
    assert blocked.action == "blocked"
    assert any(isinstance(e, Exfiltration) and e.mode == "unprotected" for e in events)
    assert not any(isinstance(e, Exfiltration) and e.mode == "protected" for e in events)
    assert any(
        isinstance(e, Step) and e.mode == "protected" and "Blocked by Ledgerline" in e.detail for e in events
    )


async def test_protected_side_keeps_a_valid_ledger_including_the_block() -> None:
    events = await run(BY_ID["silent-rug-pull"])
    entries = [e.entry.model_dump() for e in events if isinstance(e, LedgerEntry)]
    assert all(e.mode == "protected" for e in events if isinstance(e, LedgerEntry))
    assert verify_chain(entries).ok
    requests = [e for e in entries if e["kind"] == "request"]
    assert [r["decision"]["effect"] for r in requests] == ["allow", "allow", "allow", "deny"]
    assert requests[-1]["decision"]["control"] == "verify-before-call"
    assert requests[0]["tool_def_sha256"] is not None  # the pinned definition it ran under
    assert requests[0]["actor"]["agent"] == "ledgerline-sim-agent 0.1.0"


async def test_secret_never_leaves_the_sandbox() -> None:
    """The simulator uses its own temporary fake secret, never ~/.ledgerline-demo."""
    events = await run(BY_ID["tool-poisoning"])
    leaks = [e.data for e in events if isinstance(e, Exfiltration)]
    assert leaks
    assert all(leak == "FAKE_API_KEY=demo-not-a-real-key" for leak in leaks)


async def test_coverage_matrix() -> None:
    coverage = await compute_coverage(
        tuple(BY_ID[i] for i in ("rug-pull", "tool-poisoning", "baseline-weather"))
    )
    rows = {r.scenario_id: r for r in coverage.rows}
    assert rows["rug-pull"].cells == {
        "pinning": "required",
        "verify_each_call": "not_needed",
        "strict_parsing": "not_needed",
    }
    assert set(rows["tool-poisoning"].cells.values()) == {"not_stopped"}
    assert set(rows["baseline-weather"].cells.values()) == {"not_needed"}
