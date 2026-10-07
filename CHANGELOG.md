# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [v0.0.5] - 2026-10-07 — Phase 4: tamper-evident ledger

### Added
- **Tamper-evident ledger** (`ledgerline.ledger`): every `tools/call` is written to a hash-chained Postgres table **before** it is forwarded, with Ledgerline's decision (allowed, or blocked and by which control). The result is written as a linked `outcome` entry. If the entry can't be written, the call is refused (fail closed). ADR-007, ADR-009.
  - Entry format v0.1, published as `schema/event.schema.json` (generated; a test fails if it drifts): run, actor (user, agent from `clientInfo`, delegation chain), server, tool, pinned definition hash, argument digest, decision or outcome, `prev_hash`, `entry_hash`.
  - `entry_hash` = SHA-256 over RFC 8785 canonical JSON; genesis `prev_hash` is 64 zeros. The deep dive's worked example reproduces exactly (`spec/vectors/`).
  - Arguments and results are recorded as HMAC-SHA256 digests with a tenant key (`~/.ledgerline/digest.key`). Raw arguments only with `--keep-args`, in a separate table that can be erased without breaking the chain. ADR-008.
  - Postgres: append-only twice over (the `ledgerline_app` role may only insert and read; a trigger rejects UPDATE/DELETE/TRUNCATE for everyone), per-run advisory locks so concurrent writers can't fork the chain, and a migration runner.
- **`ledgerline verify --run RUN`** recomputes every hash and link and names the first entry that can't be trusted. A second, independent SQL `LAG()` check runs in the database. `ledgerline verify --file` checks an exported chain offline.
- `ledgerline ledger migrate | runs | export`, and proxy options `--ledger` (or `LEDGERLINE_DATABASE_URL`), `--run-id`, `--tenant`, `--user`, `--digest-key`, `--keep-args`.
- **Lab: the "Ledger" tab.** The protected side of every run now keeps a ledger (in memory). See the chain with its hashes, verify it with one click (checked link by link), then tamper with it (rewrite a blocked call as allowed, edit any entry's JSON, delete an entry) and watch verification fail at exactly that entry.
- `deploy/docker-compose.yml` (Postgres 16 on 127.0.0.1:55432), `make db-up`, `make db-down`, `make event-schema`, `demos/phase4.sh`.
- Tests: golden vectors, a property test (300 random one-character edits, each caught at the edited entry), fail-closed and crash-after-commit tests, and Postgres tests in a throwaway container: app role can't rewrite, owner blocked by the trigger, superuser edit caught at that entry, 50 concurrent writers produce one unbroken chain, erasing raw arguments keeps the chain valid. CI runs them against Docker and never skips them.

### Changed
- **Lab redesign.** A minimal, dark-first look (glass panels, Instrument Serif headlines, Geist text) with a light / dark / system theme switch.
- **Attack replay: a 3D attack map.** Each side of a run plays back as a knowledge graph on a tilted floor (your agent, Ledgerline, the tool server, your secrets, the attacker). A packet travels each step, a plain-language caption explains it, and you can play, pause, scrub, drag to turn the map, or switch to a flat view. The steps are derived from the run's real events (`web/src/lib/story.ts`).
- The landing page shows a looping attack map behind the headline and a one-click "Watch a silent rug pull".
- Attack map motion: each step's effects appear when its packet arrives; nothing loops forever; faster captions; drag-to-turn without re-renders, with resistance at the limits; press feedback; a gentler reduced-motion mode that updates live.

### Removed
- `--log FILE` and `proxy/jsonl_log.py`: the plain JSONL log is replaced by the ledger.
- The flow strip and attack-path components, replaced by the attack map.

## [v0.0.4] - 2026-10-03 — Phase 3: Attack Simulation Lab

### Added
- **`ledgerline ui`**: the Attack Simulation Lab in your browser (React + TypeScript, served by the Python API). Six attacks run **without and with Ledgerline side by side**: honest baseline, tool poisoning, rug pull, silent rug pull, new unreviewed tool, parser differential (duplicate keys).
  - Live animated flow (host → Ledgerline → server), an inked-in ledger timeline per side, verdicts in bookkeeping red/green, and an attack path.
  - Inspector side sheet with the raw JSON-RPC message and a plain-language explanation of each decision.
  - Defence toggles (tool pinning, check before every call, strict parsing) to re-run with any control off.
  - "What the model reads": what a person sees vs the full description, with hidden instructions highlighted and a diff against the approved version.
  - A coverage page measuring which control stops which attack, plus OWASP MCP / Agentic Top 10 tags.
  - Light and dark ledger themes, phone layout, keyboard focus, reduced-motion support.
- `ledgerline.sim`: a scripted "obedient model", a runner (unprotected and protected at the same time, through the real `StdioProxy`), typed events, a scenario catalogue and coverage measurement (ADR-006). Every scenario is a regression test.
- `ledgerline.api`: FastAPI with REST + WebSocket events, protected by `LocalGuardMiddleware` (loopback `Host` check, `Origin` check, session token exchanged for an HttpOnly cookie, CSP and other security headers).
- Proxy event hooks (`proxy/events.py`): messages per hop and which control blocked or changed what.
- `demo-rugpull --steal` and `--mode add-tool`; `LEDGERLINE_DEMO_SECRETS` sandboxing.
- UI tooling: Vite, Tailwind, Radix, TanStack Query, Biome, Vitest, Playwright; TS types generated from the Python API with CI drift checks; `make web-ci`, `make e2e`, `make ui`.

### Security
- **`ledgerline proxy http` now rejects DNS-rebinding and browser-origin requests** (foreign `Host` or any `Origin`); `--allow-host` for non-loopback deployments.


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
