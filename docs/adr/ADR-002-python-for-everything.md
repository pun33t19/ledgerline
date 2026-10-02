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
- **Merkle log:** Tessera is Go-only. Phase 8 implements the RFC 6962/9162 tree, proofs and C2SP signed-note checkpoints in Python, so we must test it against published RFC 6962 test vectors. A transparency-dev witness can still run as an external container; that's an external service, not repo code.
- **Gateway adapter:** Envoy's ext_authz is gRPC; Python's `grpcio` handles it.
- **Verifier neutrality:** a verifier in the same language as the producer proves less. Phase 12 keeps an independent, clean-room verifier with no shared code, plus language-neutral conformance vectors; a second language stays optional.
- **History:** Go tags `v0.0.0`/`v0.0.1` remain in git history for reference.

## Alternatives considered

- **Stay with Go.** Faster, and Tessera is native, but the maintainer would be learning a language and the domain at once.
- **TypeScript.** The official MCP TS SDK is good, but Python is the maintainer's strongest language and the evaluation ecosystem is Python.
