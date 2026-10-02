# ADR-004: How tool pins are enforced

- **Status:** accepted
- **Date:** 2026-10-02
- **Phase:** 2

## Context

Phase 1 showed three things: a rug pull sends no `list_changed` notification to clients that didn't subscribe; hosts may never re-list tools; and clients cache tool lists for as long as the server says. A model also *reads* tool descriptions, so a changed description can do harm even if the changed tool is never called (it can instruct the model to misuse *other* tools).

## Decision

1. **Pin whole tool definitions** (name, description, input/output schema, annotations, everything the server sends), stored in full in `ledgerline.lock` so reviewers can read exactly what was approved. Loading recomputes every hash, so a hand-edited definition can't hide behind a stale hash.
2. **Filter every `tools/list` reply:** tools that changed or were never pinned are removed before the client sees the list. Unchanged replies are forwarded byte for byte.
3. **Verify before every `tools/call`** (default): the proxy sends its own `tools/list` to the server, using the client's protocol envelope and session headers, and forwards the call only if the current definition matches the pin. Failure to verify blocks the call (fail closed).
4. **Blocked calls return a tool-level error** (`isError: true`) explaining why, so the model and the user see what happened and the session continues.
5. **No lock file means no proxy**, unless the operator opts into `--tofu` (trust on first use).
6. **`ledgerline pin` shows every new or changed definition in full** and asks for confirmation (`--yes` for scripts).

## Consequences

- Silent mid-session rug pulls (the Deadbugz pattern) are caught on the next call, even for hosts that never re-list.
- Every call costs one extra round trip to the server. `--no-verify-each-call` removes it, and a test documents that this lets a silent rug pull through. Phase 11 measures the cost.
- Pinning detects *change*, not *malice*: a server that's malicious from the start gets pinned if the reviewer approves it. Argument policies (Phase 4) and approvals (Phase 5) cover that case.
- One lock file pins one upstream server. Server names are self-reported, so they're informational only.

## Alternatives considered

- **Trust `list_changed` notifications.** They're optional and only reach subscribers (Phase 1 finding).
- **Check only listings, not calls.** Fails for hosts that never re-list (demonstrated in `tests/proxy/test_stdio_e2e.py`).
- **Pin only descriptions.** A changed input schema can add a smuggling field like `sidenote`.
- **Serve the pinned (old) definition instead of hiding the tool.** Hides the conflict from the user and keeps calling a tool whose server-side behaviour has changed.
