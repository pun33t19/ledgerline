# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed (plan)
- **The UI becomes Ledgerline's main face.** A new **Phase 3: Attack Simulation Lab** runs attacks unprotected and protected side by side in the browser, and every later phase ships its own UI slice. Phases 3–13 of the old plan are now Phases 4–14. Older changelog entries keep the numbering they were written with.
- UI stack: React + TypeScript in `web/` (ADR-005), the second exception to Python-only after the Go log service.
- Research behind the UI: `docs/research/ui-research.md` (existing tools, design principles, feature catalogue UI-01…UI-36).

### Added
- Beginner's guide PDF generator (`make guide`, `docs/guide/`).

## [v0.0.3] - 2026-10-02 — Phase 2: interceptor proxy + tool pinning

### Added
- `ledgerline` command:
  - `ledgerline pin`: fetch a server's tools, show every new or changed definition in full, and write `ledgerline.lock` after confirmation.
  - `ledgerline proxy stdio -- <cmd>`: run in front of a local MCP server.
  - `ledgerline proxy http --upstream URL`: run in front of a Streamable HTTP server (JSON and SSE replies).
  - Proxy options: `--lock`, `--tofu`, `--no-verify-each-call`, `--log`.
- Tool pinning (ADR-004): whole tool definitions are pinned with SHA-256 over RFC 8785 canonical JSON (ADR-003). Changed or unpinned tools are removed from `tools/list` replies, and calls to them are blocked with an `isError` result. The proxy re-fetches a tool's current definition before every call, so silent rug pulls are caught even when the host never re-lists.
- Strict JSON-RPC parsing (duplicate keys, `NaN`, batches, oversized messages and invalid UTF-8 are rejected), and `Mcp-Method`/`Mcp-Name` header-body checks on HTTP.
- An interceptor chain (`Forward` / `Replace` / `Block`): the plug-in point for later phases.
- A JSONL message and alert log (`--log`), temporary until the Phase 3 ledger.
- `demo-client --no-relist` (simulates a host that never re-lists) and reports for tools that appear or disappear.
- 104 tests, including byte-for-byte transparency of the Phase 1 fixtures through the proxy, the rug pull over stdio and every HTTP mode, and Hypothesis fuzzing of the parser.
- `demos/phase2.sh`, ADR-003, ADR-004 and the Phase 2 journal.

### Changed
- `Wiretap` accepts a function sink as well as a file.

## [v0.0.2] - 2026-10-02 — Phase 1 rewritten in Python

### Changed
- **The whole project is now Python** (see ADR-002). The Go code from v0.0.0–v0.0.1 is removed; its behaviour is reproduced on the official MCP Python SDK 2.2.0.
- Tooling: uv, ruff, mypy --strict, pytest, pip-audit. CI rewritten accordingly.
- Demo commands are now `demo-weather`, `demo-poisoned`, `demo-rugpull` and `demo-client` (installed into `.venv/bin` by `make install`).
- HTTP URLs now end in `/mcp` (e.g. `http://127.0.0.1:8081/mcp`).

### Added
- `demo-client --legacy` forces the pre-2026 `initialize` handshake; `testdata/mcp/weather-stdio-legacy.jsonl` captures it.

### Findings (corrected from the Go version)
- The Python SDK negotiates 2026-07-28 in both stateless and stateful HTTP mode; the Go SDK's stateful-only-2025 behaviour was SDK-specific.
- The rug pull still emits no `list_changed` notification to clients that don't subscribe.
- The SDK client caches `tools/list` by server-supplied TTL; the demo client disables the cache.

## [v0.0.1] - 2026-10-02 — Phase 1: MCP fundamentals

### Added
- Demo MCP servers built on the official Go SDK (v1.8.0), over stdio and Streamable HTTP (stateless 2026-07-28 by default, `--stateful` for 2025-11-25):
  - `weather`: an honest `get_weather` tool with canned, deterministic data.
  - `poisoned`: an `add` tool whose description hides instructions to read a fake secrets file and leak it in `sidenote` (Invariant Labs pattern).
  - `rugpull`: `get_fact_of_the_day` rewrites its own description after N calls (Deadbugz pattern).
- `demo-client`: discover/initialize → list → call, re-listing after each call to reveal changed tool definitions, with optional raw-traffic capture (`--wire`).
- `internal/wiretap`: an MCP transport wrapper that records JSON-RPC traffic as JSONL.
- Deterministic golden fixtures in `testdata/mcp/` (`make fixtures`, `make fixtures-check`).
- `demos/phase1.sh` and the Phase 1 journal.

### Findings
- Rug pulls send no `list_changed` notification to clients that don't subscribe, so pinning must check definitions on every list and every call.

## [v0.0.0] - 2026-09-30 — Phase 0: foundations

### Added
- Go module, Apache-2.0 licence, Makefile, golangci-lint v2 config and GitHub Actions CI (vet, race tests, lint, govulncheck).
- ADR template and ADR-001: Ledgerline is an evidence layer, not a gateway.
- Prior-art memo comparing Pipelock, Agent Receipts, the IETF agent-audit-trail draft, Aileron, agentgateway and ToolHive.
- `internal/version` package.
