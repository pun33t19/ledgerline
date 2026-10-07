# Phase 4 journal — Tamper-evident ledger

## Reading checklist

- [ ] Schneier & Kelsey, *Secure Audit Logs to Support Computer Forensics* (1999): hash chains, and why forward integrity matters
- [ ] AppMaster, tamper-evident audit trails in PostgreSQL: append-only roles, triggers, `LAG()` verification
- [ ] RFC 8785 (JSON Canonicalization Scheme) again: the entry hash depends on it
- [ ] NIST SP 800-92 (log management), overview chapters
- [ ] *Designing Data-Intensive Applications*, chapter 7 (transactions): why the advisory lock and the commit order matter
- [ ] psycopg 3 async docs: connections, transactions, `Jsonb`
- [ ] ADR-007 (hash chain), ADR-008 (argument digests and erasure), ADR-009 (write before forward)

## Try it yourself

```sh
./demos/phase4.sh        # needs Docker: Postgres, a silent rug pull recorded, then a superuser edit caught
./demos/phase3.sh        # the Lab: run an attack, open "Ledger", verify, tamper, verify again
```

Use the ledger with your own MCP host:

```sh
make db-up               # Postgres on 127.0.0.1:55432 + migrations
export LEDGERLINE_DATABASE_URL=postgresql://ledgerline_app:app-dev-password@127.0.0.1:55432/ledgerline
ledgerline proxy stdio --lock ledgerline.lock -- <server command>
ledgerline ledger runs
ledgerline verify --run <run id>
```

Tests: `make test` runs the Postgres tests in a throwaway container (testcontainers) when Docker is running, and skips them otherwise (CI never skips them).

## What I learned (findings from building it)

- **The deep dive's example hash reproduces exactly.** Entry 41's published `entry_hash` (`1bd152f0…f0a6`) and the tampered one (`f7f6e750…86a1`) come out byte for byte with RFC 8785 + SHA-256, so it's now an independent test vector. For that entry, sorted-key compact JSON and RFC 8785 give the same bytes; they differ only for numbers and unusual strings.
- **Where the ledger sits matters.** As one more link in the interceptor chain it would never see calls an earlier control blocked, and "Ledgerline refused this" is evidence too. So the ledger *wraps* the chain: it takes the final decision, records it, then lets the proxy act on it.
- **The verifier's check order decides where an edit is reported.** If the run-ID check came before the hash check, editing the first entry's run ID would blame the second entry. Checking the hash first means any single edit is reported at the entry that was edited; a property test makes 300 random one-character edits to prove it.
- **"Append-only" has two layers and still isn't absolute.** The app role can't `UPDATE` (privileges), the owner can't either (trigger), but a superuser can `SET session_replication_role = replica` and rewrite a row. The chain's job is to make that *visible*, and the demo does exactly that.
- **A crash right after commit means the ledger over-reports, never under-reports.** If the connection drops after the entry is committed but before the proxy forwards the call, the entry exists and the call never ran. The reverse can't happen.
- **Plain hashes of arguments leak.** A SHA-256 of `{"pin": "4821"}` falls to a 10,000-guess search, hence the keyed HMAC (ADR-008).
- **Entries survive the browser round trip.** The Lab streams entries as JSON over a WebSocket, the tamper demo edits a copy, and the server verifies it with the same code; an API test checks that the untouched copy still verifies.

## Screenshots

Take your own with `./demos/phase3.sh`: run "Silent rug pull", open "Ledger", verify, then "Tamper with the ledger".

## What surprised me

-

## Questions to carry into Phase 5

- Which argument fields should policies see in the clear, given the ledger only keeps digests?
- Should a policy decision's inputs (the rule bundle hash, matched rule) be part of `decision` in v0.1, or wait for a schema bump?
