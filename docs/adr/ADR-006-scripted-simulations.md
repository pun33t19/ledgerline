# ADR-006: The Lab runs a scripted "obedient model", not a real LLM (for now)

- **Status:** accepted
- **Date:** 2026-10-03
- **Phase:** 3

## Context

The Attack Simulation Lab must show what happens when an agent is fooled, with and without Ledgerline. A real LLM decides for itself whether to follow hidden instructions: results vary between runs and models, cost money, need an API key, and modern models often refuse the obvious demos. Ledgerline's design assumes the model *can* be fooled, so the question the Lab answers is: *if it is fooled, what stops the harm?*

## Decision

1. The Lab's agent is **scripted**: it obeys any tool description that tells it to read the bait file and pass it on, and follows "call this tool" instructions. Every run is deterministic, free, offline and identical in CI.
2. Each run executes **unprotected and protected at the same time**. The protected side goes through the **real `StdioProxy`** with the selected controls, so the Lab exercises production code, not a mock.
3. **Every scenario is a regression test** (`tests/sim/test_scenarios.py`), and the coverage matrix is *measured* by re-running with each control off.
4. Each run gets a **sandbox**: a temporary fake secret (`LEDGERLINE_DEMO_SECRETS`) and per-side attacker logs. Nothing touches the user's home folder.
5. The agent speaks JSON-RPC itself (not through the SDK client), so scenarios can also send hand-crafted messages, such as the duplicate-key parser attack.
6. A **live-model mode** (a real LLM, with transcript and cost cap) is planned for Phase 11 (UI-12), clearly labelled as such.

## Consequences

- Results are reproducible and safe to show anywhere, including a public demo.
- The Lab says "the agent is scripted to obey" on its first screen, so nobody mistakes it for a measurement of model behaviour.
- Scenarios stay close to documented incidents (Invariant, Deadbugz) but are simplified. Benchmarks (Phase 11) carry the quantitative claims.

## Alternatives considered

- **Real LLM from the start:** non-deterministic, costly, and refusals hide what Ledgerline does.
- **Recorded transcripts only:** not interactive, and can't show what happens when you toggle a control.
