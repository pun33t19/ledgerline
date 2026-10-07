# ADR-007: Ledger v1 is a hash chain in Postgres, one chain per proxy session

- **Status:** accepted
- **Date:** 2026-10-07
- **Phase:** 4

## Context

Every tool call needs a record that can't be quietly changed afterwards. A log file can be edited by anyone with access to it (the Phase 2 `--log` file was exactly that). The deep dive and the AppMaster pattern describe a Postgres table where each row carries the previous row's hash, the application role may only insert, and a verifier recomputes the chain. The IETF agent-audit-trail draft also chains SHA-256 over RFC 8785 canonical JSON. Phase 9 adds a Merkle log on top. This phase needs the format and the chain to be right, because Phase 9 commits to these hashes.

## Decision

1. **Entry format v0.1** (`ledger/schema.py`, published as `schema/event.schema.json`). Every field is always present, `null` where it doesn't apply yet, so the hashed bytes never depend on which optional fields a writer chose to emit. There are two kinds of entry: `request` (the call and Ledgerline's decision) and `outcome` (what came back, linked by `request_hash`).
2. **Hashing:** `entry_hash = SHA-256(RFC 8785(entry without entry_hash))`, the same canonicalisation as tool pins (ADR-003). `prev_hash` is inside the hashed bytes.
3. **Genesis `prev_hash` is 64 zeros**, not `null` as the IETF draft has it. A fixed-length hex value keeps every link the same shape and type, and it matches the deep dive's worked example, which we reproduce byte for byte as an independent test vector (`spec/vectors/deep-dive-entry-41.json`).
4. **One chain per proxy session** (`run_id`, default: time plus random). Concurrent writers to one chain are serialised with `pg_advisory_xact_lock(hashtextextended(run_id, 0))` held until commit. `UNIQUE (run_id, prev_hash)` makes a fork impossible even if the lock were bypassed.
5. **Append-only, twice over:** the `ledgerline_app` role gets only `INSERT, SELECT`, and a trigger rejects `UPDATE`, `DELETE` and `TRUNCATE` for everyone. A superuser can still disable triggers. That isn't prevented, but it is *detected*: `ledgerline verify` recomputes every hash.
6. **Two independent checks in `verify`:** recomputing hashes in Python (catches edits, deletions, reordering) and a SQL `LAG()` query over the stored columns (catches removed or reordered rows, without trusting Python).
7. **Lab runs use an in-memory store** with the same sealing and the same verifier, so `ledgerline ui` still needs no database and the tamper demo exercises the real code.

## Consequences

- An insider with database access can still delete *the whole run*, or rewrite every entry and recompute every hash. A chain detects partial edits, not wholesale replacement. Witnessed checkpoints (Phase 9) close that gap.
- Appends to one run are serial. That's fine for one agent session; the Phase 12 load tests measure it.
- Entries are stored as `jsonb`. Postgres normalises key order and whitespace, which doesn't matter because the hash is over the canonical form, not the stored text.

## Alternatives considered

- **`null` genesis (IETF draft).** Equivalent in strength; we kept the deep dive's zeros so its published example verifies unchanged.
- **One global chain for all runs.** Simpler to anchor later, but every writer in the system would serialise on one lock. Per-run chains are combined in the Phase 9 Merkle log instead.
- **Append to a file and sign each line.** Signatures prove who wrote an entry, not that none were removed. The chain gives ordering and completeness; signatures come with checkpoints in Phase 9.
- **SQLite for the CLI.** Would avoid Docker for local use, but the roles, triggers and concurrency behaviour we want to demonstrate are Postgres's. The in-memory store covers the no-database case.
