# ADR-003: RFC 8785 canonical JSON for every hash

- **Status:** accepted
- **Date:** 2026-10-02
- **Phase:** 2

## Context

Ledgerline fingerprints JSON: tool definitions now, ledger entries and arguments from Phase 4 on. A fingerprint is only useful if *anyone* (an auditor's tool, a verifier in another language, a future version of Ledgerline) computes the same bytes from the same data. Ordinary JSON serialisation varies: key order, whitespace, number formatting (`1.0` vs `1`, `1e30` vs `1e+30`), and string escaping all differ between libraries and settings. Phase 1's demo client used `json.dumps(sort_keys=True)`, which fixes key order only.

## Decision

Every hash in Ledgerline is `SHA-256(RFC 8785(value))`, using the [JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785) via the `rfc8785` package. Values that can't be canonicalised (for example integers beyond ±2^53) are treated as failures: the tool is refused rather than hashed some other way.

## Consequences

- Fingerprints are reproducible in any language with a JCS library. The IETF agent-audit-trail draft and Agent Receipts use JCS too, which eases Phase 13 mapping.
- A server that sends huge integers in a tool definition can't be pinned. That's acceptable: fail closed.
- `ledgerline pin` and the proxy must hash the *raw* JSON from the wire, not SDK objects (which can add or drop fields). Both do.

## Alternatives considered

- **`json.dumps(sort_keys=True, separators=(",", ":"))`.** Python-specific number and escape formatting; another language could disagree.
- **Hash the raw bytes as received.** Breaks on harmless re-serialisation (key order, whitespace) between server, SDK and proxy, causing false alarms.
