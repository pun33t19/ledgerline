# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Ledgerline is an authorization and evidence layer for AI-agent tool calls. It sits as a proxy between an MCP client and an MCP server and checks every message. Today it pins tool definitions and records every tool call in a hash-chained ledger before forwarding it; later phases add policy, approval, a Merkle log and A2A. The roadmap and per-phase scope live in `docs/roadmap.md`, and decisions are recorded in `docs/adr/`.

## Languages

- Python for everything (`src/ledgerline/`), using uv, ruff, `mypy --strict` and pytest with anyio.
- Exceptions:
  - the UI in `web/` is React 19 + TypeScript (ADR-005);
  - the Phase 9 transparency-log service `tlogd/` will be Go (ADR-002 amendment).
- Don't introduce other languages.

## Commands

### Python

```bash
make install          # uv sync
make ci               # lint + typecheck + test (what must be green)
make lint             # ruff check + ruff format --check   (make fmt to fix)
make typecheck        # mypy strict over src + tests
make test             # uv run pytest
make fixtures-check   # re-record testdata/mcp and fail on any diff (CI runs it)
make vuln             # pip-audit
make demo PHASE=4     # demos/phase4.sh (needs Docker)
make db-up            # local Postgres ledger + migrations (make db-down to stop)
make event-schema     # regenerate schema/event.schema.json
make guide            # beginner's guide PDF (uv group "guide", ReportLab)
```

Run a single Python test:

```bash
uv run pytest tests/sim/test_scenarios.py::test_outcomes_match_the_scenario -k rug-pull
```

### Web (`web/`, Node 24)

```bash
make web-install      # npm ci
make web-types        # export FastAPI OpenAPI -> regenerate web/src/api/schema.d.ts
make web-ci           # type-drift check, Biome, tsc, Vitest, build
make e2e              # build UI, then Playwright (web/e2e)
make ui               # build UI, then `uv run ledgerline ui`
```

Run a single web test:

```bash
cd web && npx vitest run src/lib/runState.test.ts
cd web && npx playwright test -g "coverage"
```

For UI development with hot reload, run the API with `uv run ledgerline ui --dev --no-browser --port 8765` and, in parallel, `cd web && npm run dev`. Vite proxies `/api`, including WebSockets, to 8765.

## Architecture

### Proxy core (`proxy/`, `jsonrpc.py`)

- Both transports feed every message through one interceptor `Chain` (`proxy/interceptor.py`):
  - `StdioProxy` spawns the server and relays its stdin/stdout.
  - The Streamable HTTP proxy (`proxy/http.py`, on Starlette + httpx) handles both JSON and SSE replies.
- An interceptor's `on_request` and `on_response` return `Forward`, `Replace(body)` or `Block(response)`. Requests run through the chain in order and responses in reverse; `observe` only watches.
- Interceptors can make their own upstream calls through the `Upstream` protocol. For example, the pin check re-fetches `tools/list` before every call. These calls use random-prefixed ids so they never collide with the client's ids.
- `ProxyEvents` (`proxy/events.py`) are hooks for the UI and simulator to see hops, decisions and alerts. They don't affect forwarding.
- `jsonrpc.parse` is strict on purpose, to avoid parser differentials. It rejects duplicate keys, NaN, batches and messages over 16 MiB.
- Both protocol versions must work:
  - the 2026-07-28 version: stateless `server/discover`, a `params._meta` envelope, and `Mcp-Method`/`Mcp-Name` headers that must match the body;
  - the legacy 2025-11-25 version with `initialize`.

### Pinning (`pin/`)

- `ledgerline pin` fetches the tools and fingerprints each definition as SHA-256 over RFC 8785 canonical JSON. It writes a lock file that holds the full definitions, so changes can be diffed.
- At runtime, `PinInterceptor` hides changed or unpinned tools from `tools/list`.
- It also blocks calls to them, and by default re-verifies the live definition before every call. That per-call check is what stops a silent rug pull.
- The default is fail closed: if the upstream check can't run, the call is blocked.

### Ledger (`ledger/`)

- `LedgerInterceptor` **wraps** the inner chain (it is not one more link): it takes the chain's final decision on each `tools/call`, appends a `request` entry (including blocks, as `deny` with the control), and only then returns the decision, so the proxy forwards after the commit. A failed write returns `Block` with control `ledger` (fail closed). Replies produce a linked `outcome` entry.
- Entry format v0.1 is `ledger/schema.py`; every field is always present (nulls), because the hashed bytes must not depend on omitted fields. `schema/event.schema.json` is generated: run `make event-schema` after changing the model (a test checks drift).
- `hashing.seal`: `entry_hash` = SHA-256 of RFC 8785 JSON without `entry_hash`; genesis `prev_hash` is 64 zeros. `verify.verify_chain` works on raw dicts; its check order (fields, seq, link, hash, run, references) is what makes a single edit reported at the edited entry. Don't reorder it.
- Stores: `PostgresStore` (advisory lock per run, append-only table + trigger, `ledgerline_app` role with INSERT/SELECT) and `MemoryStore` (Lab runs, tests). Migrations are `ledger/migrations/NNNN_*.sql`, applied by `ledgerline ledger migrate` as the owner.
- Arguments/results are HMAC digests (`digest.py`, key at `~/.ledgerline/digest.key`); raw args only with `--keep-args` into the erasable `ledger_args` table.
- Golden vectors in `spec/vectors/` (one is the deep dive's example, computed independently) must keep verifying; don't regenerate them to make a test pass.

### Attack Simulation Lab (`sim/`)

- A `Scenario` (`sim/catalog.py`) pairs a demo server with scripted agent steps and the expected verdicts.
- `Runner` runs each scenario in two lanes at the same time:
  - **unprotected**: the agent talks to the server directly;
  - **protected**: traffic goes through the real `StdioProxy` with the chosen `Controls`.
- The agent (`sim/agent.py`) is a deterministic stand-in for a hijacked model: it always obeys "read X and pass it as 'arg'" instructions.
- A fake secret lives in a temp sandbox, passed to servers through `LEDGERLINE_DEMO_SECRETS`. Harm is detected by watching the demo server's exfil log.
- Every scenario is also a regression test (`tests/sim/test_scenarios.py`). The coverage matrix (`sim/coverage.py`) is measured by actually running every scenario with each control switched off.

### API and UI (`api/`, `web/`)

- `ledgerline ui` serves a FastAPI app on 127.0.0.1 (`api/app.py`): REST endpoints plus a WebSocket at `/api/runs/{id}/events`.
- `LocalGuardMiddleware` (`api/security.py`) protects it:
  - Host and Origin checks against DNS rebinding;
  - a startup token exchanged for an HttpOnly cookie;
  - CSP.
- `ledgerline proxy http` uses the same guard.
- On the web side, `useRunEvents` → `lib/runState.ts` (`applyEvent` reducer) → pages and components. The typed `RunEvent` union in `sim/events.py` is the contract.
- The protected lane wraps its chain in `LedgerInterceptor` with a `MemoryStore`; entries stream as `ledger_entry` events. The Ledger tab's tamper demo edits a copy in the browser and posts it to `POST /api/ledger/verify`.
- The run page's 3D attack map (`components/AttackStage.tsx`) plays back beats built by `lib/story.ts`, a pure function over one side's events. If a scenario's steps or event wording change, update `story.ts` and `story.test.ts` to match.
- `web/src/api/schema.d.ts` is generated: never edit it by hand. Run `make web-types` after changing any API or pydantic model, and commit the result, because CI fails on drift.
- The built UI goes to `src/ledgerline/api/static/` (gitignored).

## Invariants and gotchas

- **Postgres tests** (`tests/ledger/test_postgres.py`, `test_proxy_ledger.py`) start `postgres:16-alpine` via testcontainers and skip when Docker isn't running, unless `LEDGERLINE_REQUIRE_DOCKER=1` (set in CI). Local DB for manual use: `make db-up` (127.0.0.1:55432; dev passwords in `deploy/docker-compose.yml`).

- **Transparency:** with no interceptors that intervene, the proxy must forward bytes unchanged. `make fixtures-check` re-records `testdata/mcp/*.jsonl`, both direct and through the proxy, and they must stay byte-identical.
- The malicious demo servers (`demo/servers/poisoned.py`, `rugpull.py`) must only ever target the fake bait secrets file.
- TypeScript is pinned to `~5.9`, because openapi-typescript breaks on TS 7.
- Playwright uses port `LEDGERLINE_E2E_PORT` (default 8781) and the token `playwright-test-token`. Don't use 8799: an unrelated local process uses it.
- `docs/guide/build_guide.py` has a `FILES` dict that must describe every tracked file. Update it when adding files.
- Commits are authored by the maintainer only. **Never add Claude co-author or "Generated with" lines** to commits or PRs.

## Per-phase conventions

Each phase ends with:
- `make ci`, `make web-ci` and e2e green;
- an ADR for any real trade-off;
- `demos/phaseN.sh`;
- `docs/journal/phaseN.md`;
- a `CHANGELOG.md` entry;
- the guide extended (`make guide`);
- the roadmap status updated;
- a `__version__` bump and the next patch tag (Phase 5 → v0.0.6).

From Phase 3 on, every phase also ships a UI slice (feature IDs `UI-xx` in `docs/research/ui-research.md`) with a Playwright test for its main flow.
