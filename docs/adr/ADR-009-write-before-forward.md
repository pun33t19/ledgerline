# ADR-009: Write before forward, and fail closed

- **Status:** accepted
- **Date:** 2026-10-07
- **Phase:** 4

## Context

A record written *after* a call can be lost: the process crashes, the database is briefly down, or the connection drops between the tool running and the log write. Then the most important calls, the ones that did something, are the ones missing from the evidence. Blocked calls matter too: "Ledgerline refused this" is evidence that the control worked.

## Decision

1. **The ledger wraps the interceptor chain** instead of being one link in it. It asks the inner chain (pins today; policy and approvals later) for its decision, then writes a `request` entry with that decision, and only then returns it, so the proxy forwards or refuses the call afterwards. Calls another control blocks are recorded too (as `deny`, with the control and reason).
2. **The entry is committed before the call is forwarded.** If writing it fails for any reason, the call is **not** forwarded: the client gets a tool error ("this call could not be recorded in the ledger, so it was not run").
3. **The outcome is written after the reply arrives**, linked to its request by `request_hash`. If *that* write fails, the call has already happened, so the reply still goes back to the client and the failure is logged. A request without an outcome means "we know it was attempted; we didn't record the result".
4. **The proxy refuses to start** if `--ledger` is given but the database can't be reached.
5. Without `--ledger`, the proxy still runs, with a warning that calls aren't recorded.

## Consequences

- A crash between commit and forward leaves an entry for a call that never ran. The ledger can over-report an attempt, never under-report one (tested in `tests/ledger/test_interceptor.py`).
- Every call waits for one database commit (a few milliseconds locally). Phase 12 measures it under load.
- Availability now depends on the database. That's deliberate for an evidence layer: an unrecorded action is worse than a refused one.

## Alternatives considered

- **Write after the call (or asynchronously).** Faster, but the records most likely to be lost are the consequential ones.
- **Fail open (forward when the ledger is down).** Turns a database outage into a silent evidence gap. Phase 5's ADR may allow fail-open for explicitly read-only tools; the default stays closed.
- **Make the ledger the first link in the chain.** It would record calls before knowing whether they'd be blocked, needing a second entry for the decision.
