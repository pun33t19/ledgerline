# ADR-008: Arguments are recorded as keyed digests; raw arguments are optional and erasable

- **Status:** accepted
- **Date:** 2026-10-07
- **Phase:** 4

## Context

The ledger should prove *what* a call was asked to do without becoming a second copy of every secret, email address and query that passed through it. A plain SHA-256 of arguments doesn't hide short values: anyone can hash every 4-digit PIN or every name in a phone book and compare. Privacy law (India's DPDP Act, GDPR) also expects personal data to be erasable, but nothing may ever be removed from a hash chain.

## Decision

1. **`args_digest = HMAC-SHA256(tenant key, RFC 8785(arguments))`** and the same for results (`outcome.result_digest`). Without the key, a digest can't be recomputed or brute-forced; with it, an auditor can confirm that given arguments match an entry.
2. **The key lives outside the database:** by default `~/.ledgerline/digest.key`, 32 random bytes, created with mode `0600` on first use (`--digest-key` to choose another file). Lab runs use a random key per run.
3. **Raw arguments are not stored by default.** With `--keep-args` they go into `ledger_args`, a separate table keyed by `(run_id, seq)`. The application role may delete from it, so erasure is a plain `DELETE` and every hash in the chain stays valid.

## Consequences

- Losing the key means digests can no longer be checked against candidate arguments; the chain itself still verifies. Back the key up like any other secret.
- Rotating the key changes digests from then on. Phase 13's spec will add a key identifier to entries; v0.1 doesn't have one yet.
- Erasing arguments removes the ability to show *what* was sent, while keeping proof *that* it was sent, when, by whom, and what was decided.

## Alternatives considered

- **Plain SHA-256 (as in the deep dive's illustration).** Reversible for low-entropy arguments.
- **Encrypt raw arguments inside the entry.** Erasure would then mean destroying a key per entry (crypto-shredding). Possible later; a separate table is simpler and easier to audit now.
- **Store nothing about arguments.** Then the ledger couldn't answer "was it *this* query?", which is the point of Phase 5's argument-level policies.
