# ADR-002: Python for the whole project

- **Status:** accepted (supersedes the Go-first choice in the original plan)
- **Date:** 2026-10-02
- **Phase:** 1

## Context

The original plan used Go for the proxy and ledger core, TypeScript/Next.js for the console, and Python only for benchmarks. Phases 0–1 were first built in Go.

The project is also a learning curriculum, and the maintainer understands Python much better than Go. One language across proxy, ledger, console, evaluation and verifier means one toolchain, one test framework, and code the maintainer can read and change confidently.

Python now has what the plan needs:

| Need | Python option |
|---|---|
| MCP client/server, 2026-07-28 incl. `server/discover`, stdio + Streamable HTTP | Official `mcp` SDK 2.2.0 (verified in Phase 1) |
| Policy engine (Cedar) | `cedarpy` (Rust Cedar bindings) |
| Postgres ledger | `psycopg` 3 (async) |
| Durable approvals | Temporal Python SDK |
| OpenTelemetry | `opentelemetry-sdk` |
| Ed25519, hashing | `cryptography`, `hashlib` |
| RFC 8785 canonical JSON | `rfc8785` package |
| Console + API | FastAPI + server-rendered templates (htmx) |
| Benchmarks | AgentDojo (already Python) |

## Decision

Use **Python (3.12+, developed on 3.14)** for all Ledgerline code: proxy, ledger, policy, approvals, telemetry, Merkle log, console, CLI, evaluation and verifier.

Tooling: `uv` (environments, lockfile), `ruff` (lint and format), `mypy --strict`, `pytest` with the anyio plugin, `pip-audit`.

## Consequences

- **Easier:** one language; the official MCP SDK is the reference implementation; AgentDojo and the eval harness share code with the product.
- **Performance:** Python adds more latency per call than Go. The plan's targets are relaxed to **p50 < 10 ms, p99 < 50 ms added per `tools/call`** and **≥ 500 ledger appends/s per chain**, and Phase 11 measures them. Mitigations: asyncio throughout, `uvloop`, batched commits, and keeping crypto in C/Rust-backed libraries.
- **Merkle log:** Tessera is Go-only. See the amendment below: Phase 8 is the one place Go is used.
- **Gateway adapter:** Envoy's ext_authz is gRPC; Python's `grpcio` handles it.
- **Verifier neutrality:** a verifier in the same language as the producer proves less. Phase 12 keeps an independent, clean-room verifier with no shared code, plus language-neutral conformance vectors. The Merkle layer gets a true cross-language check (Go builds, Python verifies).
- **History:** Go tags `v0.0.0`/`v0.0.1` remain in git history for reference.

## Alternatives considered

- **Stay with Go.** Faster, and Tessera is native, but the maintainer would be learning a language and the domain at once.
- **TypeScript.** The official MCP TS SDK is good, but Python is the maintainer's strongest language and the evaluation ecosystem is Python.

## Amendment (2026-10-02): Go for the Phase 8 log service only

**Decision.** The transparency log is a separate service, `tlogd/`, written in Go on [Tessera](https://github.com/transparency-dev/tessera). It is the only Go code in the repository, and it has its own `go.mod`. Python code submits entries to it over HTTP and verifies its checkpoints and proofs independently.

**Why.**
- Tessera is production-proven (it backs Sigstore's Rekor v2) and implements the C2SP tlog-tiles, checkpoint and witness formats. Hand-rolling a Merkle log and signed notes in Python is the most error-prone part of the project.
- A separate process keeps the signing key and the log's history outside the agent host's and proxy's reach.
- Go building the log and Python verifying it gives two independent RFC 6962 implementations that must agree, which is stronger evidence than one language checking itself.

**Cost.** A second toolchain from Phase 8 on (Go job in CI, one more container in compose), and roughly 300–500 lines of Go the maintainer must be able to read. The Go stays deliberately thin: glue around Tessera, no business logic.
