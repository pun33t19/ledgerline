# Ledgerline — Phase-by-Phase Roadmap

## Context

`Ledgerline beginner deep dive.md` proposes **Ledgerline**, an open-source *gateway-neutral evidence layer* for AI-agent actions. It sits between an agent host and its tools (MCP) / peer agents (A2A) and:

1. **Intercepts** every `tools/call` (and A2A `SendMessage`) — the Policy Enforcement Point (PEP).
2. **Decides** via an embedded policy engine (Cedar) with argument-level rules + session taint — the PDP.
3. **Pauses** risky calls for durable human approval (timeout = deny).
4. **Records** every call, decision, approval and delegation hop in a tamper-evident ledger (hash chain → Merkle transparency log with signed, witnessed checkpoints).
5. **Proves** it: an offline `ledgerline verify` CLI, and a UI that makes all of this visible.
6. **Shows** it: the **UI is the product's main face**. It opens with an Attack Simulation Lab that runs real attacks with and without Ledgerline side by side, then grows each phase (evidence explorer, policy studio, approval inbox, Merkle visualizer, delegation graph, benchmark dashboards). Research: [research/ui-research.md](research/ui-research.md).

The honest novelty is *not* "a signed agent log" or "an MCP firewall with receipts" (Pipelock already ships rug-pull detection, tool policy, taint, HITL modes, signed receipts with four verifiers and a dashboard; see the 2026-10-03 re-check in prior-art.md). Ledgerline is an **authorization + evidence layer**, complementary to egress firewalls like Pipelock. It is the combination of: (a) a neutral event schema mapped to OTel GenAI / Agent Receipts / IETF agent-audit-trail, (b) a witnessed Merkle log with offline proofs, (c) MCP↔A2A delegation lineage, (d) signed policy-decision + approval provenance. **Never claim "first tamper-evident agent firewall."** See [prior-art.md](prior-art.md).

**Decisions:** **Python for everything** (ADR-002), with two exceptions: the Phase 9 transparency-log service `tlogd` in **Go** on Tessera (ADR-002 amendment), and the **UI in React + TypeScript** under `web/` (ADR-005, 2026-10-03). UI work starts in Phase 3 and every later phase ships a UI slice (decided 2026-10-03; phases after 2 were renumbered +1). Full roadmap before the first public release (repo `pun33t19/ledgerline` stays private until Phase 14). ~20–25 h/week, ~28–30 weeks total. Commits authored only by the maintainer, never with Claude attribution.

**Status:** Phase 0 ✅ (v0.0.0) · Phase 1 ✅ (Go v0.0.1, rewritten in Python as v0.0.2) · Phase 2 ✅ (v0.0.3) · next: Phase 3, Attack Simulation Lab.

---

## Stack

| Concern | Choice |
|---|---|
| Language / tooling | Python 3.12+ (dev on 3.14), `uv`, `ruff`, `mypy --strict`, `pytest` + anyio plugin, `pip-audit` |
| MCP | Official `mcp` SDK 2.2.0 (`MCPServer`, `Client`, stdio + Streamable HTTP, 2026-07-28 + legacy) |
| Proxy I/O | `anyio` subprocess pipes (stdio relay); Starlette ASGI app + `httpx` streaming client (HTTP reverse proxy) |
| Canonical JSON | `rfc8785` (RFC 8785 JCS) |
| Ledger store | Postgres 16 via `psycopg` 3 (async) + plain-SQL migrations applied by a small runner |
| Property / integration tests | `hypothesis`, `testcontainers` |
| Policy | `cedarpy` (Cedar); YAML policy test cases |
| Approvals | Temporal Python SDK (`temporalio`), with its time-skipping test environment |
| Telemetry | `opentelemetry-sdk` (+ `InMemorySpanExporter` in tests) |
| UI (ADR-005) | **React 19 + TypeScript** (strict), Vite, Tailwind CSS + Radix (shadcn/ui pattern), React Flow (`@xyflow/react`) for flows and graphs, Motion, Recharts, TanStack Query, Monaco, React Router; Biome lint; Vitest + Testing Library; Playwright e2e. Node 24 + npm |
| UI API | FastAPI (REST + WebSocket event streams) in `src/ledgerline/api/`; TS types generated with `openapi-typescript` (CI fails on drift); `ledgerline ui` serves API + built UI on 127.0.0.1 with a startup token and `Origin`/`Host` checks |
| Simulations | `src/ledgerline/sim/`: typed scenarios, scripted "hijacked model" agent, runner (unprotected vs protected), event sink interceptor; every scenario is also a pytest regression case |
| Merkle log | **Go exception:** `tlogd`, a small Go service on Tessera (C2SP tlog-tiles, signed checkpoints, witness cosigning) with an HTTP API; Python talks to it with `httpx` and verifies proofs independently in `ledgerline.tlog` |
| A2A | Official `a2a-sdk` |
| Eval | AgentDojo (Python), MCPTox |
| Load | `locust` + `pytest-benchmark` |
| Gateway adapter | `grpcio` Envoy ext_authz service |
| Docs / release | MkDocs Material; PyPI trusted publishing; Sigstore signing; CycloneDX SBOM; container image |

**Performance targets** (relaxed for Python per ADR-002): policy eval p99 < 1 ms; added latency per `tools/call` p50 < 10 ms, p99 < 50 ms; ≥ 500 ledger appends/s per chain; Merkle checkpoint lag 1–5 s.

## Repository layout (target)

```
ledgerline/
  pyproject.toml, uv.lock, Makefile
  src/ledgerline/
    cli.py                 # `ledgerline` command: proxy, pin, verify, policy, approvals, worker, serve, export, keygen
    jsonrpc.py             # JSON-RPC 2.0 parsing, framing, id correlation
    proxy/                 # interceptor.py, stdio.py, http.py
    pin/                   # canonical.py, lockfile.py, interceptor.py
    ledger/                # schema.py, hashing.py, digest.py, store.py, verify.py, interceptor.py, migrations/
    policy/                # engine.py, bundle.py, interceptor.py, testrunner.py
    taint.py
    approval/              # workflow.py, activities.py, worker.py, interceptor.py
    telemetry.py
    tlog/                  # client.py (talks to tlogd), verify.py (independent RFC 6962 proof + checkpoint checks), integrator.py
    a2a/                   # proxy.py, lineage.py
    api/                   # FastAPI app for the UI: REST + WebSocket, serves web/dist (Phase 3)
    sim/                   # attack simulation engine: scenarios, scripted agent, runner, events (Phase 3)
    extauthz/              # gRPC ext_authz service
    demo/                  # demo servers + client (Phase 1) ✅
    wiretap.py             # ✅
  web/                     # React + TypeScript UI (Vite); src/{pages,components,api,features}, e2e/ (Phase 3)
  tlogd/                   # Go transparency-log service on Tessera (own go.mod), Phase 9
  schema/event.schema.json # PUBLIC event schema
  spec/                    # spec, conformance vectors, mapping tables
  tests/                   # unit, property, integration, e2e
  eval/                    # benchmark harness (uv dependency group "eval")
  load/                    # locustfiles
  deploy/docker-compose.yml
  docs/{adr,journal,research,guide}/, docs/roadmap.md, docs/prior-art.md
  demos/phaseN.sh
```

## How each phase is structured

**Read** (study first) → **Changes** (➕ added / ✏️ modified / ➖ removed, with descriptions; the PR description) → **What's new** (changelog entry) → **Test** → **Exit / demo**.

## Conventions (every phase)

- Ends with: `make ci` green (ruff, mypy strict, pytest) plus `make fixtures-check` and `make vuln` in CI; from Phase 3 also `make web-ci` (Biome, `tsc`, Vitest, build, type-drift check) and Playwright; an ADR for any real trade-off; `demos/phaseN.sh`; `docs/journal/phaseN.md` with UI screenshots; a `CHANGELOG.md` entry; the beginner's guide PDF extended (`make guide`); bump `__version__` and tag the next patch version (Phase 3 → v0.0.4, …).
- **UI slice rule:** from Phase 3, every phase ships the UI for what it builds (feature IDs `UI-xx` from `docs/research/ui-research.md`), designed with the `frontend-design` skill, with a Playwright test for its main flow. Polish and the app shell land in Phase 8.
- Testing pyramid: parametrized unit tests → `hypothesis` property/fuzz tests on every parser and on ledger/crypto invariants → `testcontainers` integration (Postgres, Temporal) → end-to-end demo scripts → benchmarks and load tests.
- Commits: Conventional Commits, authored by the maintainer only.

---

## Phase 0 — Environment, scope & prior art ✅ (v0.0.0)

Repo, Apache-2.0, ADR-001 (evidence layer, not a gateway), `docs/prior-art.md` (checked 2026-09-30), CI. Toolchain converted to Python in v0.0.2.

## Phase 1 — MCP fundamentals ✅ (v0.0.2)

Demo servers `demo-weather`, `demo-poisoned`, `demo-rugpull`, `demo-client` (`--wire`, `--legacy`), `ledgerline.wiretap`, deterministic fixtures in `testdata/mcp/`, `demos/phase1.sh`. Findings: both handshakes must be supported; rug pulls send no `list_changed` to non-subscribers; clients cache `tools/list` by server TTL, so pin what the server sends.

---

## Phase 2 — Interceptor (PEP) + tool-definition pinning ✅ (v0.0.3)

`ledgerline pin` / `proxy stdio` / `proxy http`; `jsonrpc.py` (strict parsing: duplicate keys, NaN, batches and oversized messages rejected); `proxy/` (interceptor chain with Forward/Replace/Block, stdio relay, HTTP proxy with SSE, JSONL log); `pin/` (RFC 8785 fingerprints, lock file with full definitions, pin interceptor). Changed or unpinned tools are hidden from listings and blocked on call; the current definition is re-fetched before every call (ADR-003, ADR-004). 104 tests incl. byte-identical fixture replay through the proxy. Findings: per-call verification is what stops a silent rug pull; pinning detects change, not malice. Details in `CHANGELOG.md` and `docs/journal/phase2.md`.

---

## Phase 3 — Attack Simulation Lab v1 (Weeks 5–7) ★ new

The UI's first and most visible piece. It runs the attacks we already have **unprotected and protected, side by side**, animating every message and naming the control that intervened. It also closes the DNS-rebinding gap found during the Phase 2 review.

**Read:** React docs ("Learn" section) and TypeScript handbook (basics, narrowing); Vite guide; React Flow quickstart; TanStack Query overview; FastAPI WebSockets; OWASP MCP Top 10 and OWASP Agentic Top 10 (ASI); MITRE ATLAS overview; DVMCP challenge list; evidence-first approval pattern (`docs/research/ui-research.md`); MCP spec security guidance on `Origin` validation and DNS rebinding.

**Changes:**

| | Path | Description |
|---|---|---|
| ➕ | `src/ledgerline/sim/scenario.py` | Typed `Scenario`: id, title, category, difficulty, framework tags (OWASP MCP, ASI, ATLAS), incident mirrored, server command, scripted agent steps, expected unprotected and protected outcomes, controls that matter |
| ➕ | `src/ledgerline/sim/catalog.py` | v1 scenarios: tool poisoning (honest limit: pinning approves it as-is), rug pull (re-listing host), silent rug pull (host never re-lists), new unreviewed tool appears mid-session, parser differential (duplicate keys), oversized message, HTTP header/body mismatch |
| ➕ | `src/ledgerline/sim/agent.py` | Scripted "hijacked model": obeys tool descriptions (reads the **fake** secret, fills the smuggling field); deterministic and free |
| ➕ | `src/ledgerline/sim/runner.py` | Runs a scenario unprotected (direct) and protected (real `StdioProxy`/`HttpProxy` with chosen controls); watches the exfil log; produces a verdict per mode |
| ➕ | `src/ledgerline/sim/events.py` + `proxy/events.py` | Typed event stream (`message`, `decision`, `alert`, `exfiltration`, `step`, `outcome`) from an `EventSink` interceptor; async bus |
| ✏️ | `demo/servers/rugpull.py` | `--mode add-tool` (adds an unreviewed tool instead of rewriting one) |
| ➕ | `src/ledgerline/api/app.py`, `api/routes/*.py` | FastAPI: `GET /api/scenarios`, `POST /api/runs`, `WS /api/runs/{id}/events`, `GET /api/runs/{id}`, `GET /api/pins`, `POST /api/pins/approve`, `GET /api/coverage`; serves `web/dist` |
| ➕ | `src/ledgerline/api/security.py` | 127.0.0.1 binding, random startup token (printed link, Jupyter-style), `Origin`/`Host` validation, CSP headers |
| ✏️ | `proxy/http.py` | Same `Origin`/`Host` validation for `ledgerline proxy http` (DNS-rebinding fix) |
| ➕ | `ledgerline ui` (`cli.py`) | Starts API + UI and opens the browser |
| ➕ | `web/` (Vite + React + TS) | App shell; **Lab** page (scenario catalogue, UI-01); **Run** page: split-screen unprotected vs protected (UI-02), animated React Flow message flow (UI-03), timeline + raw-message inspector (UI-04), defence toggles (UI-05), kill-chain strip (UI-09); **Tool view**: model's-eye vs user's-eye (UI-06) and pinned-vs-current diff with approve (UI-07); **Coverage** heatmap scenarios × controls × OWASP/ATLAS (UI-08); basic pinned-server list (UI-25); dark/light theme (UI-34) |
| ➕ | `web/src/api/schema.d.ts` | Generated from FastAPI's OpenAPI (`make web-types`); CI fails on drift |
| ➕ | `tests/sim/test_scenarios.py` | **Every scenario is a regression test**: asserts the unprotected and protected outcomes |
| ➕ | `tests/api/`, `web/src/**/*.test.tsx`, `web/e2e/lab.spec.ts` | API + WebSocket tests; component tests; Playwright: run "silent rug pull" in the UI → protected side shows "Blocked by pin check" |
| ✏️ | CI, Makefile | `web` job (npm ci, Biome, `tsc`, Vitest, build, Playwright, type-drift check); `make ui`, `make web-ci`, `make web-types` |
| ➕ | ADR-005 (UI stack, accepted), ADR-006 scripted vs live-model simulations | |
| ✏️ | `docs/guide/` | New section: the UI architecture and "React + TypeScript for Java developers" |

**What's new:** `ledgerline ui` opens an Attack Simulation Lab where anyone can watch an attack succeed without Ledgerline and fail with it, see exactly which control stopped it, inspect every message, and see coverage against OWASP/ATLAS. The local HTTP surfaces resist DNS rebinding.
**Test:** scenario outcomes in pytest (both modes); API/WebSocket tests; Vitest; Playwright e2e; `Origin`/`Host` tests for UI and proxy; screenshots in the journal.
**Exit:** `demos/phase3.sh` launches the lab; a recorded walkthrough of "silent rug pull" side by side. Tag v0.0.4.

---

## Phase 4 — Ledger v1: hash-chained Postgres + `verify` (Weeks 8–9)

**Read:** Schneier & Kelsey; AppMaster tamper-evident Postgres pattern; RFC 8785; NIST SP 800-92 overview; DDIA transactions chapter; psycopg 3 async docs.

**Changes:**

| | Path | Description |
|---|---|---|
| ➕ | `src/ledgerline/ledger/schema.py` | Pydantic `Event` v0: `schema_version, seq, ts, run_id, tenant, actor{user, agent, on_behalf_of_chain}, protocol, method, server, tool, tool_def_sha256, args_digest, result_digest, session_taint, decision, approval, trace_id, prev_hash, entry_hash` (`decision`/`approval` optional until Phases 5–6) |
| ➕ | `schema/event.schema.json` | Generated from the model; a test fails if it drifts |
| ➕ | `src/ledgerline/ledger/hashing.py` | `entry_hash = SHA-256(JCS(entry minus entry_hash))`; genesis `prev_hash` per ADR (IETF draft uses `null`) |
| ➕ | `src/ledgerline/ledger/digest.py` | `args_digest = HMAC-SHA256(tenant key, JCS(args))`; a plain SHA-256 of short args is brute-forceable |
| ➕ | `src/ledgerline/ledger/migrations/0001_ledger.sql` + `migrate.py` | `ledger_entries`; `ledger_args_encrypted` (deletable, for DPDP erasure); UPDATE/DELETE-blocking trigger; `ledgerline_app` role with INSERT/SELECT only; tiny migration runner |
| ➕ | `src/ledgerline/ledger/store.py` | Async append in a transaction under `pg_advisory_xact_lock(chain_id)`; reads by run/range |
| ➕ | `src/ledgerline/ledger/verify.py` + `ledgerline verify --run` | Recompute every hash and link; report first broken seq; plus a SQL `LAG()` comparison query |
| ➕ | `src/ledgerline/ledger/interceptor.py` | **Write-before-forward**: commit `request` entry before forwarding, `outcome` entry after |
| ✏️ | proxy chain | pin → ledger |
| ➖ | `proxy/jsonl_log.py` | Replaced by the ledger |
| ➕ | `deploy/docker-compose.yml` | Postgres 16 |
| ➕ | `spec/vectors/chain-001.json` | Golden entries + expected hashes (first try reproducing the deep-dive's example hashes) |
| ➕ | **UI slice** | Ledger explorer per run (UI-15); hash-chain visualizer with **live tamper demo**: edit an entry and watch verification fail at that link (UI-16); animated one-click verify (UI-17); Lab runs now write ledger entries and link to them |
| ➕ | ADRs: args HMAC + erasure; write-before-forward | |

**What's new:** every intercepted call leaves a hash-chained, append-only record written *before* the call runs; `ledgerline verify` proves the chain intact or pinpoints the edit, and the UI shows it happening.
**Test:** golden vectors; `hypothesis`: any single-byte edit fails verify at exactly that seq; 50 concurrent appenders → contiguous valid chain; testcontainers: app-role UPDATE rejected, superuser UPDATE caught; crash between commit and forward → entry exists, tool never ran; Playwright: tamper demo turns the chain red at the edited entry.
**Exit:** `demos/phase4.sh` tampers as superuser; CLI and UI point to the break. Tag v0.0.5.

---

## Phase 5 — Policy engine (PDP), taint & decision provenance (Weeks 10–11)

**Read:** Anderson *Security Engineering* (access control); Cedar paper; Progent; *Capability Myths Demolished*; Beurer-Kellner *Design Patterns*; ToolHive Cedar docs; `cedarpy` README.

**Changes:**

| | Path | Description |
|---|---|---|
| ➕ | `src/ledgerline/policy/engine.py` | Wraps `cedarpy`. Entities User/Agent/Team/Tool; action `call_tool`; context `{args, session_taint, approved_by_human}`; returns `allow` / `deny` / `needs_approval`; default deny |
| ➕ | `src/ledgerline/policy/bundle.py` | Loads policy dir; `policy_bundle_sha256` over sorted canonical files |
| ➕ | `src/ledgerline/policy/interceptor.py` | Fills `decision{effect, engine, engine_version, policy_bundle_sha256, input_digest, matched_rules}` |
| ➕ | `src/ledgerline/taint.py` | Per-run taint; config lists tools/servers whose output is untrusted |
| ➕ | `src/ledgerline/policy/testrunner.py` + `ledgerline policy test` | YAML cases → expected effect |
| ➕ | `examples/policies/support.cedar`, `cases.yaml` | The deep-dive's permit/forbid rules |
| ➕ | `src/ledgerline/demo/servers/fake_supabase.py` (`demo-fake-supabase`), `fake_mail.py`, `fake_github.py` | Realistic targets for injection scenarios |
| ✏️ | schema | `decision` required; `session_taint` enum |
| ✏️ | proxy chain | pin → taint → policy → ledger; `needs_approval` = deny until Phase 6 |
| ➕ | **New Lab scenarios** | Supabase token theft (indirect injection via ticket), postmark-style silent BCC, GitHub public-issue → private-repo leak, shadowing; the Phase 3 tool-poisoning scenario now **blocked** by argument rules (UI-11 incident replays) |
| ➕ | **UI slice** | Policy studio: Cedar editor (Monaco) + test runner (UI-21); what-if evaluator (UI-22); taint visualizer (UI-23); policy change review flagging widened permissions (UI-24); **scenario builder** for custom attacks saved as regression cases (UI-10) |
| ➕ | ADR: fail-closed default | Fail-closed for write/send tools; configurable fail-open for read-only |

**What's new:** versioned, testable, argument-level rules; taint after untrusted content; every entry records which rulebook version and rule decided; policies can be written, tested and what-if'd in the UI.
**Test:** parametrized policy tests; `policy test` in CI; Step 14 scenario (ticket read allowed → tainted → `select * from integration_tokens` = `needs_approval`); `pytest-benchmark` p99 < 1 ms; injected engine error → recorded deny; Playwright: what-if evaluator and scenario builder.
**Exit:** hijacked query blocked with matched rule + bundle hash in the ledger, shown side by side in the Lab. Tag v0.0.6.

---

## Phase 6 — Durable human approval (Weeks 12–13)

**Read:** Temporal Python HITL tutorial and "HITL for MCP tools"; Temporal docs on signals, timers, determinism, idempotency; MCP Multi Round-Trip Requests; evidence-first approval card pattern.

**Changes:**

| | Path | Description |
|---|---|---|
| ➕ | `src/ledgerline/approval/workflow.py` | `ApprovalWorkflow`: `workflow.wait_condition` on a `decision` signal with `approval_timeout`; timeout = deny |
| ➕ | `src/ledgerline/approval/activities.py` | Write approval ledger entry; notify proxy |
| ➕ | `src/ledgerline/approval/worker.py` + `ledgerline worker` | Runs the Temporal worker |
| ➕ | `src/ledgerline/approval/interceptor.py` | On `needs_approval`: start workflow, hold the request (each client request in its own task, fixing the Phase 2 stdio queueing limitation), then forward or return `isError` citing ledger seq |
| ➕ | idempotency key per call | At-most-once forwarding |
| ➕ | `ledgerline approvals list / approve / deny --reason` | CLI alongside the UI |
| ✏️ | schema | `approval{by, decision, at, reason, workflow_id, decision_entry_hash}` |
| ✏️ | compose | Temporal dev server + UI |
| ➕ | **UI slice** | **Approval inbox with evidence-first cards**: action → evidence (failed or missing checks as ✗ rows) → agent verdict collapsed → approve/deny; full arguments; tainting content; matched rule; timeout countdown; keyboard shortcuts (UI-26); approval history linked to ledger entries (UI-27); Lab scenarios can pause for *your* approval |

**What's new:** risky calls pause for a human decision that survives crashes; silence = deny; reviewers see evidence before verdicts; every decision is in the ledger, linked to the policy decision it answered.
**Test:** `temporalio.testing.WorkflowEnvironment` time-skipping: approve, deny, timeout→deny; chaos: kill worker mid-wait, restart, approve → demo server counter shows exactly 1 execution; proxy restart recovers pending approvals; Playwright: approve/deny from the inbox.
**Exit:** chaos demo + inbox walkthrough. Tag v0.0.7.

---

## Phase 7 — Observability with OpenTelemetry (Week 14)

**Read:** OTel primer; OTel GenAI + MCP semconv (`semantic-conventions-genai`); W3C Trace Context. (Note: the MCP Python SDK already has `mcp/server/_otel.py`; read it.)

**Changes:** `src/ledgerline/telemetry.py` (OTLP setup; spans `tools/call <tool>`; policy + approval child spans; `traceparent` read/inject in `params._meta`); ledger stores `trace_id/span_id`; compose adds OTel Collector + Jaeger; ADR: traces are not evidence. **UI slice:** live traffic monitor (calls/s, blocks, alerts feed, added latency, links to traces) (UI-28).
**What's new:** decisions appear in existing tracing dashboards under the same trace ID as the ledger entry, and live in Ledgerline's own monitor.
**Test:** `InMemorySpanExporter` assertions on names/attributes/parents; manual Jaeger check; Vitest for monitor widgets. Tag v0.0.8.

---

## Phase 8 — App shell, auth & auditor workflows (Weeks 15–16)

Replaces the old "auditor console" phase: the views exist by now, so this phase makes them one polished product.

**Read:** OAuth 2.1 / OIDC basics for SPAs (authorization code + PKCE); OWASP ASVS (web auth sections); WCAG 2.2 essentials; the `frontend-design` skill.

**Changes:** unified navigation and design system pass (UI-34); OIDC login for shared deployments, keeping the local token mode (UI-36); roles (viewer, approver, admin); pinned-server registry and settings (UI-25); **evidence report export** of a run or campaign as HTML/PDF (UI-14); guided tours and glossary pop-overs for beginners (UI-35); accessibility audit (keyboard paths, contrast, reduced motion); full Playwright suite of the Step 14 walkthrough; `ledgerline serve` for shared deployments.
**What's new:** one coherent, authenticated application for operators, approvers and auditors.
**Test:** Playwright across roles; axe accessibility checks in CI; auth tests (token, OIDC mock). Exit: screen recording of the full walkthrough. Tag v0.0.9.

---

## Phase 9 — Ledger v2: Merkle transparency log (Weeks 17–19)

**Language note:** this phase adds the project's Go code, `tlogd/`, so the log is built on Tessera (the library behind Sigstore's Rekor v2) instead of a hand-rolled tree. Everything that *uses* or *checks* the log stays in Python (and, in the browser, TypeScript). The log is built by Go code and checked by separately written Python and TypeScript code: independent implementations of RFC 6962.

**Read:** Crosby & Wallach; RFC 6962 + RFC 9162 (tree hashing, inclusion/consistency proofs, STH); C2SP `tlog-tiles`, `signed-note`, `tlog-checkpoint`, `tlog-witness`; Tessera README + codelab; Rekor v2 GA post; *Tour of Go* (just enough Go for ~300–500 lines); Merkle 1987 (skim).

**Changes:**

| | Path | Description |
|---|---|---|
| ➕ | `tlogd/go.mod`, `tlogd/main.go` | Go service (own module) wrapping Tessera with the POSIX storage driver. Exposes `POST /add` (leaf = ledger `entry_hash`, returns leaf index once integrated), serves the standard C2SP **tlog-tiles** static API (`/checkpoint`, `/tile/...`) that any tlog client can read |
| ➕ | `tlogd/signer.go` | Ed25519 note signer for checkpoints (`golang.org/x/mod/sumdb/note`); key from a file created by `ledgerline keygen` |
| ➕ | `tlogd/witness.go` | Sends new checkpoints to a witness (C2SP tlog-witness) and serves the cosigned checkpoint |
| ➕ | `tlogd/*_test.go`, `tlogd/Dockerfile` | Go tests (add → integrate → proof); container image for compose |
| ➕ | `src/ledgerline/tlog/client.py` | Python `httpx` client: submits entry hashes to `tlogd`, fetches checkpoints and tiles |
| ➕ | `src/ledgerline/tlog/verify.py` | **Independent** Python verification: RFC 6962 leaf/node hashing (0x00/0x01), inclusion and consistency proofs computed from tiles, checkpoint signature check with `cryptography` Ed25519 |
| ➕ | `src/ledgerline/tlog/integrator.py` | Background task: sends committed ledger entries to `tlogd`, records `(seq → leaf_index)` and checkpoints in Postgres |
| ➕ | `ledgerline keygen`, `ledgerline export --run X`, `ledgerline verify --offline bundle.json` | Key generation; export of entries + proofs + cosigned checkpoint; offline verification with no server or DB |
| ✏️ | migrations `0002_tlog.sql`; compose adds `tlogd` + a witness container |
| ✏️ | CI | Adds a Go job for `tlogd/` (`go vet`, `go test -race`, `govulncheck`) |
| ✏️ | Makefile | `make tlogd` (build), `make tlogd-test` |
| ➕ | **UI slice** | Merkle tree visualizer with inclusion-proof path and consistency proof between checkpoints (UI-18); witness and checkpoint status (UI-19); **drag-and-drop offline verifier running in the browser** in TypeScript, a third independent implementation (UI-20) |
| ➕ | ADRs: hash chain + Merkle; tlogd as a separate Go service | Why both layers are kept; why the log runs as its own process (the signing key and log history sit outside the agent host's and proxy's reach) |

**What's new:** compact inclusion proofs, witnessed signed checkpoints (no split views), fully offline audit on the same log library Sigstore uses, and proofs you can *see*.
**Test:** Go: Tessera integration tests in `tlogd/`. Python and TypeScript verifiers against **RFC 6962 / transparency-dev published test vectors** and against live `tlogd` proofs (cross-implementation); `hypothesis`: inclusion for random leaves, consistency as the tree grows; split-view checkpoint rejected by the witness; tampered bundle fails offline verify in CLI and browser; `tlogd` down → ledger keeps appending and the integrator catches up; measure checkpoint lag and proof size.
**Exit:** offline verify on a machine without DB access, from the CLI and by dropping a bundle into the browser. Tag v0.0.10.

---

## Phase 10 — A2A delegation lineage (Weeks 20–21)

**Read:** A2A spec v1.0; A2A enterprise guidance; A2ABreak; South et al.; RFC 8693 (`act` claim); WIMSE/AIMS draft; `a2a-sdk` docs.

**Changes:** `src/ledgerline/a2a/proxy.py` (intercept `SendMessage` + task lifecycle, ledger events with `protocol: "a2a"`); `a2a/lineage.py` (propagate `on_behalf_of_chain` + `parent_entry_hash` in metadata; map OAuth `act` claims); MCP calls inherit A2A task lineage; schema adds `parent_entry_hash`, `a2a{task_id, state, agent_card_sha256}`, `delegation_depth`; `src/ledgerline/demo/agents/` (agent A → agent B → fake-supabase). **UI slice:** interactive delegation graph with identity-loss highlights (UI-29); multi-agent Lab scenarios.
**What's new:** user → agent A → agent B → tool reconstructed from the ledger alone and drawn as a graph; identity loss at any hop flagged.
**Test:** 3-process demo rebuilt from ledger only; A2ABreak "identity dropped mid-chain" flagged; agent-card hash pinning; Playwright: graph renders the chain. Tag v0.0.11.

---

## Phase 11 — Security evaluation & regression corpus (Weeks 22–23)

**Read:** AgentDojo, MCPTox, MCPSecBench, MCP-SafetyBench; Nasr et al.; Qin et al.; Auditable Agents.

**Changes:** `eval/` (uv dependency group `eval`): AgentDojo suites wrapped as MCP servers behind Ledgerline; baseline vs Ledgerline runs with pinned models/seeds (utility, utility under attack, ASR); MCPTox runner; published eval policies. Lab scenarios become the incident regression corpus (Deadbugz, postmark BCC, GitHub toxic flow, Supabase token theft). `tests/tamper/` (agent with shell tries to delete/spoof its trace; external ledger + witness catch it). `docs/eval-report.md`, `docs/auditability-card.md`. **UI slice:** benchmark dashboard comparing published defences (UI-30); **live-model mode** in the Lab, running scenarios against a real LLM with transcript and cost cap (UI-12); **challenge mode** to get an attack past Ledgerline, with a local leaderboard (UI-13); coverage heatmap extended to full OWASP/ATLAS mapping (UI-08).
**What's new:** reproducible security claims ("under these benchmarks"), a permanent incident regression suite, and attacks you can try yourself.
**Test:** incident + tamper suites in CI; benchmark eval manual/nightly (token budget); live-model mode behind an explicit opt-in with a key. Tag v0.0.12.

---

## Phase 12 — Performance & gateway adapter (Weeks 24–25)

**Read:** DDIA stream processing; *Building Secure and Reliable Systems* (recovery); Envoy `ext_authz`; agentgateway / ContextForge (Python) plugin docs.

**Changes:** `demo-echo` server baseline; `load/locustfile.py` scenarios; `py-spy`/`cProfile` profiling and fixes (uvloop, batched commits, connection pooling); `src/ledgerline/extauthz/` gRPC ext_authz service + `ledgerline extauthz`; `deploy/agentgateway/` compose example; optional ContextForge plugin; optional outbox → NATS only if measured need; `docs/load-report.md`. **UI slice:** performance dashboard (UI-31); UI performance budget (bundle size, WebSocket throughput under load).
**What's new:** Ledgerline plugs into existing gateways; overhead measured, published and visible.
**Test:** targets from the Stack section; adapter integration test in compose; Lighthouse/bundle-size check in CI. Tag v0.0.13.

---

## Phase 13 — Schema spec, independent verifiers & upstream (Week 26)

**Read:** IETF agent-audit-trail draft (latest); Agent Receipts spec; OTel semconv contribution guide.

**Changes:** `spec/ledgerline-event-v0.1.md` (normative: fields, canonicalisation, hashing, checkpoint format, verification algorithm); frozen `schema/event.schema.json` v0.1; `spec/vectors/*.json` conformance vectors (valid/tampered chains, proofs, checkpoints, expected results); `verifiers/reference/`, an **independent clean-room verifier**; the browser TypeScript verifier (Phase 9) also runs every vector, giving independent implementations in three languages (Go builds, Python and TypeScript verify); `spec/mappings/{otel-genai,agent-receipts,ietf-agent-audit-trail}.md`. **UI slice:** schema explorer with field docs and live examples (UI-32).
**What's new:** a documented, testable format any implementation can verify. Exit: upstream issue/PR opened. Tag v0.0.14.

---

## Phase 14 — Open-source launch v0.1.0 (Weeks 27–28)

**Read:** OpenSSF Scorecard checks; opensource.guide; PyPI trusted publishing; Sigstore Python; SLSA levels.

**Changes:** README built from **`docs/readme-blueprint.md`** (Pipelock-style structure: problem → verify it yourself → Lab GIF → quick start → measured results with honest-assessment notes → comparison vs Pipelock/gateways/scanners/guardrails → features by pillar → **hand-crafted SVG architecture diagrams D1–D7** with text fallbacks → OWASP/ATLAS coverage → testing/assurance → licence), with every competitor claim re-verified on launch day; MkDocs Material site (concepts, quickstart, policy guide, spec, ADR index, FAQ vs Pipelock/agentgateway); `demos/quickstart.sh` (`docker compose up` + open the Lab in < 5 min); **public hosted demo**: a read-only Lab with recorded runs (UI-33); CONTRIBUTING (DCO), CODE_OF_CONDUCT, SECURITY, GOVERNANCE, MAINTAINERS; issue/PR templates, Dependabot (pip + npm + Go); release workflow (PyPI trusted publishing, Sigstore-signed artifacts, CycloneDX SBOM for Python and npm, container image with the built UI); CodeQL (Python, TypeScript, Go) + Scorecard workflows; CHANGELOG v0.1.0; launch essay and demo video.
**What's new:** public, signed, documented v0.1.0 whose first impression is the Lab. **Test:** fresh-machine quickstart < 5 min; signatures verify; Scorecard ≥ 7. **Exit:** repo public, tag v0.1.0, essay, HN post 17:30–22:30 IST.

---

## Verification (end-to-end, from Phase 8 onward)

1. `docker compose -f deploy/docker-compose.yml up -d` (Postgres, Temporal, Collector/Jaeger, `tlogd`, witness).
2. `make ci` (ruff, mypy strict, pytest incl. hypothesis + testcontainers).
3. `demos/supabase.sh` (and the same scenario in the Lab): allowed ticket read → taint → hijacked query → `needs_approval` → deny in the approval inbox → agent gets `isError`.
4. `ledgerline verify --run <id>` passes; `export` + `verify --offline` passes; superuser UPDATE → verify fails at that seq.
5. Playwright e2e (Lab, ledger explorer, approval inbox, Merkle viewer) and the incident corpus pass; Jaeger trace ID equals ledger `trace_id`.
