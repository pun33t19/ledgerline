# Ledgerline — Phase-by-Phase Roadmap (Python)

## Context

`Ledgerline beginner deep dive.md` proposes **Ledgerline**, an open-source *gateway-neutral evidence layer* for AI-agent actions. It sits between an agent host and its tools (MCP) / peer agents (A2A) and:

1. **Intercepts** every `tools/call` (and A2A `SendMessage`) — the Policy Enforcement Point (PEP).
2. **Decides** via an embedded policy engine (Cedar) with argument-level rules + session taint — the PDP.
3. **Pauses** risky calls for durable human approval (timeout = deny).
4. **Records** every call, decision, approval and delegation hop in a tamper-evident ledger (hash chain → Merkle transparency log with signed, witnessed checkpoints).
5. **Proves** it: an auditor console and an offline `ledgerline verify` CLI.

The honest novelty is *not* "a signed agent log" (Pipelock, Agent Receipts, Aileron already do that). It is the combination of: (a) a neutral event schema mapped to OTel GenAI / Agent Receipts / IETF agent-audit-trail, (b) a witnessed Merkle log with offline proofs, (c) MCP↔A2A delegation lineage, (d) signed policy-decision + approval provenance. **Never claim "first tamper-evident agent firewall."** See [prior-art.md](prior-art.md).

**Decisions:** **Python for everything** (ADR-002, 2026-10-02; replaced the original Go/TypeScript plan), **except the Phase 8 transparency-log service `tlogd`, written in Go on Tessera** (ADR-002 amendment, 2026-10-02). Full roadmap before the first public release (repo `pun33t19/ledgerline` stays private until Phase 13). ~20–25 h/week. Commits authored only by the maintainer, never with Claude attribution.

**Status:** Phase 0 ✅ (v0.0.0) · Phase 1 ✅ (Go v0.0.1, rewritten in Python as v0.0.2).

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
| Console | FastAPI + Jinja2 templates + htmx; `pytest-playwright` for e2e |
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
    console/               # FastAPI app, templates/, static/
    extauthz/              # gRPC ext_authz service
    demo/                  # demo servers + client (Phase 1) ✅
    wiretap.py             # ✅
  tlogd/                   # the ONLY Go code: transparency-log service on Tessera (own go.mod), Phase 8
  schema/event.schema.json # PUBLIC event schema
  spec/                    # spec, conformance vectors, mapping tables
  tests/                   # unit, property, integration, e2e
  eval/                    # benchmark harness (uv dependency group "eval")
  load/                    # locustfiles
  deploy/docker-compose.yml
  docs/{adr,journal}/, docs/roadmap.md, docs/prior-art.md
  demos/phaseN.sh
```

## How each phase is structured

**Read** (study first) → **Changes** (➕ added / ✏️ modified / ➖ removed, with descriptions; the PR description) → **What's new** (changelog entry) → **Test** → **Exit / demo**.

## Conventions (every phase)

- Ends with: `make ci` green (ruff, mypy strict, pytest) plus `make fixtures-check` and `make vuln` in CI; an ADR for any real trade-off; `demos/phaseN.sh`; `docs/journal/phaseN.md`; a `CHANGELOG.md` entry; bump `__version__` and tag the next patch version (Phase 2 → v0.0.3, Phase 3 → v0.0.4, …).
- Testing pyramid: parametrized unit tests → `hypothesis` property/fuzz tests on every parser and on ledger/crypto invariants → `testcontainers` integration (Postgres, Temporal) → end-to-end demo scripts → benchmarks and load tests.
- Commits: Conventional Commits, authored by the maintainer only.

---

## Phase 0 — Environment, scope & prior art ✅ (v0.0.0)

Repo, Apache-2.0, ADR-001 (evidence layer, not a gateway), `docs/prior-art.md` (checked 2026-09-30), CI. Toolchain converted to Python in v0.0.2.

## Phase 1 — MCP fundamentals ✅ (v0.0.2)

Demo servers `demo-weather`, `demo-poisoned`, `demo-rugpull`, `demo-client` (`--wire`, `--legacy`), `ledgerline.wiretap`, deterministic fixtures in `testdata/mcp/`, `demos/phase1.sh`. Findings: both handshakes must be supported; rug pulls send no `list_changed` to non-subscribers; clients cache `tools/list` by server TTL, so pin what the server sends.

---

## Phase 2 — Interceptor (PEP) + tool-definition pinning (Weeks 3–4)

**Read:** DDIA 2e (log/storage chapters); MCP transports (stdio framing, Streamable HTTP/SSE, `Mcp-Method`/`Mcp-Name` headers, stateless core); `sparfenyuk/mcp-proxy` (Python!) source; ETDI paper; Trail of Bits `mcp-context-protector`; anyio subprocess and streams docs.

**Changes:**

| | Path | Description |
|---|---|---|
| ➕ | `src/ledgerline/jsonrpc.py` | JSON-RPC 2.0 message classification (request/notification/response/error), newline framing over raw bytes, request↔response id correlation |
| ➕ | `src/ledgerline/proxy/interceptor.py` | `Interceptor` protocol (`on_request` / `on_response` → `Forward`, `Block(error)` or later `Hold`) and a chain that runs several in order. The seam every later phase plugs into |
| ➕ | `src/ledgerline/proxy/stdio.py` | Spawns the real server, relays stdin/stdout byte lines both ways with anyio, parses each line for the interceptor chain, forwards original bytes unchanged |
| ➕ | `src/ledgerline/proxy/http.py` | Starlette app reverse-proxying Streamable HTTP (incl. SSE) via `httpx`; checks `Mcp-Method`/`Mcp-Name` match the body (2026-07-28) and rejects mismatches |
| ➕ | `src/ledgerline/pin/canonical.py`, `lockfile.py` | RFC 8785 canonical JSON (`rfc8785`), SHA-256 of each **whole** tool definition, read/write `ledgerline.lock` |
| ➕ | `src/ledgerline/pin/interceptor.py` | Hashes every `tools/list` response; re-checks the pin before forwarding each `tools/call`; on mismatch blocks with a JSON-RPC error result and logs an alert |
| ➕ | `src/ledgerline/proxy/jsonl_log.py` | Temporary JSONL message log (replaced in Phase 3) |
| ➕ | `src/ledgerline/cli.py` + `[project.scripts] ledgerline` | `ledgerline proxy stdio -- <cmd>`, `ledgerline proxy http --upstream URL --listen :PORT`, `ledgerline pin -- <cmd>` |
| ➕ | `tests/proxy/`, `tests/pin/` | Replay, property, integration and rug-pull tests |
| ➕ | `docs/adr/ADR-003-canonical-json-rfc8785.md` | Why JCS for all hashing |
| ➕ | `demos/phase2.sh` | Pin `demo-rugpull`, run 4 calls through the proxy, 4th blocked |

**What's new:** Ledgerline runs as a transparent proxy in front of any stdio or HTTP MCP server, logs every message, and blocks rug pulls by pinning whole tool definitions.
**Test:** fixture replay through the relay with raw-byte equality; `hypothesis` fuzzing of the parser (malformed lines, huge lines, mismatched ids); integration (demo-client → proxy → demo-weather) for both handshakes; rug-pull test (4th call blocked) over stdio and HTTP; header/body mismatch rejected; manual: Claude Code configured with `ledgerline proxy stdio -- .venv/bin/demo-weather` works unchanged.
**Exit:** a changed tool description gets blocked. Tag v0.0.3.

---

## Phase 3 — Ledger v1: hash-chained Postgres + `verify` (Weeks 5–6)

**Read:** Schneier & Kelsey; AppMaster tamper-evident Postgres pattern; RFC 8785; NIST SP 800-92 overview; DDIA transactions chapter; psycopg 3 async docs.

**Changes:**

| | Path | Description |
|---|---|---|
| ➕ | `src/ledgerline/ledger/schema.py` | Pydantic `Event` v0: `schema_version, seq, ts, run_id, tenant, actor{user, agent, on_behalf_of_chain}, protocol, method, server, tool, tool_def_sha256, args_digest, result_digest, session_taint, decision, approval, trace_id, prev_hash, entry_hash` (`decision`/`approval` optional until Phases 4–5) |
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
| ➕ | ADR-004 args HMAC + erasure; ADR-005 write-before-forward | |

**What's new:** every intercepted call leaves a hash-chained, append-only record written *before* the call runs; `ledgerline verify` proves the chain intact or pinpoints the edit.
**Test:** golden vectors; `hypothesis`: any single-byte edit fails verify at exactly that seq; 50 concurrent appenders → contiguous valid chain; testcontainers: app-role UPDATE rejected, superuser UPDATE caught; crash between commit and forward → entry exists, tool never ran.
**Exit:** `demos/phase3.sh` tampers as superuser; verify points to the break. Tag v0.0.4.

---

## Phase 4 — Policy engine (PDP), taint & decision provenance (Weeks 7–8)

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
| ➕ | `src/ledgerline/demo/servers/fake_supabase.py` (`demo-fake-supabase`) | SQLite `execute_sql` with `tickets`, `integration_tokens`, poisoned ticket #8812 |
| ✏️ | schema | `decision` required; `session_taint` enum |
| ✏️ | proxy chain | pin → taint → policy → ledger; `needs_approval` = deny until Phase 5 |
| ➕ | ADR-006 fail-closed default | Fail-closed for write/send tools; configurable fail-open for read-only |

**What's new:** versioned, testable, argument-level rules; taint after untrusted content; every entry records which rulebook version and rule decided.
**Test:** parametrized policy tests; `policy test` in CI; Step 14 scenario (ticket read allowed → tainted → `select * from integration_tokens` = `needs_approval`); `pytest-benchmark` p99 < 1 ms; injected engine error → recorded deny.
**Exit:** hijacked query blocked with matched rule + bundle hash in the ledger. Tag v0.0.5.

---

## Phase 5 — Durable human approval (Weeks 9–10)

**Read:** Temporal Python HITL tutorial and "HITL for MCP tools"; Temporal docs on signals, timers, determinism, idempotency; MCP Multi Round-Trip Requests.

**Changes:**

| | Path | Description |
|---|---|---|
| ➕ | `src/ledgerline/approval/workflow.py` | `ApprovalWorkflow`: `workflow.wait_condition` on a `decision` signal with `approval_timeout`; timeout = deny |
| ➕ | `src/ledgerline/approval/activities.py` | Write approval ledger entry; notify proxy |
| ➕ | `src/ledgerline/approval/worker.py` + `ledgerline worker` | Runs the Temporal worker |
| ➕ | `src/ledgerline/approval/interceptor.py` | On `needs_approval`: start workflow, hold the request, then forward or return `isError` citing ledger seq |
| ➕ | idempotency key per call | At-most-once forwarding |
| ➕ | `ledgerline approvals list / approve / deny --reason` | CLI until the console exists |
| ✏️ | schema | `approval{by, decision, at, reason, workflow_id, decision_entry_hash}` |
| ✏️ | compose | Temporal dev server + UI |

**What's new:** risky calls pause for a human decision that survives crashes; silence = deny; every decision is in the ledger, linked to the policy decision it answered.
**Test:** `temporalio.testing.WorkflowEnvironment` time-skipping: approve, deny, timeout→deny; chaos: kill worker mid-wait, restart, approve → demo server counter shows exactly 1 execution; proxy restart recovers pending approvals.
**Exit:** chaos demo. Tag v0.0.6.

---

## Phase 6 — Observability with OpenTelemetry (Week 11)

**Read:** OTel primer; OTel GenAI + MCP semconv (`semantic-conventions-genai`); W3C Trace Context. (Note: the MCP Python SDK already has `mcp/server/_otel.py`; read it.)

**Changes:** `src/ledgerline/telemetry.py` (OTLP setup; spans `tools/call <tool>`; policy + approval child spans; `traceparent` read/inject in `params._meta`); ledger stores `trace_id/span_id`; compose adds OTel Collector + Jaeger; ADR-007 traces are not evidence.
**What's new:** decisions appear in existing tracing dashboards under the same trace ID as the ledger entry.
**Test:** `InMemorySpanExporter` assertions on names/attributes/parents; manual Jaeger check. Tag v0.0.7.

---

## Phase 7 — Auditor console (Week 12)

**Read:** FastAPI docs (dependencies, background tasks); htmx docs; Invariant's finding that confirmation dialogs hide full input ("show everything"). Load the `frontend-design` skill before designing pages.

**Changes:** `src/ledgerline/console/` FastAPI app — JSON API (runs, timeline, entry detail with decrypted args for authorised viewers, pending approvals, POST approve/deny, POST verify) and server-rendered pages: `/runs`, `/runs/{id}`, `/approvals` (full args, tainting content, matched rule), verify button; dev bearer-token auth; `ledgerline serve`; `tests/e2e/test_supabase_walkthrough.py` (pytest-playwright).
**What's new:** approvals and audits in a browser, including one-click chain verification.
**Test:** API tests with FastAPI `TestClient`; Playwright e2e of the full Step 14 walk-through. Exit: screen recording. Tag v0.0.8.

---

## Phase 8 — Ledger v2: Merkle transparency log (Weeks 13–15)

**Language note:** this phase adds the project's only Go code, `tlogd/`, so the log is built on Tessera (the library behind Sigstore's Rekor v2) instead of a hand-rolled tree. Everything that *uses* or *checks* the log stays in Python. The log is built by Go code and checked by separately written Python code: two independent implementations of RFC 6962.

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
| ✏️ | migrations `0002_tlog.sql`; compose adds `tlogd` + a witness container; console verify panel shows checkpoint + cosigners |
| ✏️ | CI | Adds a Go job for `tlogd/` (`go vet`, `go test -race`, `govulncheck`); Python CI unchanged |
| ✏️ | Makefile | `make tlogd` (build), `make tlogd-test` |
| ➕ | ADR-008 hash chain + Merkle; ADR-009 tlogd as a separate Go service | Why both layers are kept; why the log runs as its own process (the signing key and log history sit outside the agent host's and proxy's reach) |

**What's new:** compact inclusion proofs, witnessed signed checkpoints (no split views), and fully offline audit, on the same log library Sigstore uses.
**Test:** Go: Tessera integration tests in `tlogd/`. Python: `verify.py` against **RFC 6962 / transparency-dev published test vectors**, and against proofs produced by a live `tlogd` (cross-implementation check); `hypothesis`: inclusion for random leaves, consistency as the tree grows; split-view checkpoint rejected by the witness; tampered bundle fails offline verify; `tlogd` down → ledger keeps appending (hash chain) and the integrator catches up; measure checkpoint lag and proof size.
**Exit:** offline verify on a machine without DB access. Tag v0.0.9.

---

## Phase 9 — A2A delegation lineage (Weeks 16–17)

**Read:** A2A spec v1.0; A2A enterprise guidance; A2ABreak; South et al.; RFC 8693 (`act` claim); WIMSE/AIMS draft; `a2a-sdk` docs.

**Changes:** `src/ledgerline/a2a/proxy.py` (intercept `SendMessage` + task lifecycle, ledger events with `protocol: "a2a"`); `a2a/lineage.py` (propagate `on_behalf_of_chain` + `parent_entry_hash` in metadata; map OAuth `act` claims); MCP calls inherit A2A task lineage; schema adds `parent_entry_hash`, `a2a{task_id, state, agent_card_sha256}`, `delegation_depth`; `src/ledgerline/demo/agents/` (agent A → agent B → fake-supabase); console delegation-graph view.
**What's new:** user → agent A → agent B → tool reconstructed from the ledger alone; identity loss at any hop flagged.
**Test:** 3-process demo rebuilt from ledger only; A2ABreak "identity dropped mid-chain" flagged; agent-card hash pinning. Tag v0.0.10.

---

## Phase 10 — Security evaluation & regression corpus (Weeks 18–19)

**Read:** AgentDojo, MCPTox, MCPSecBench, MCP-SafetyBench; Nasr et al.; Qin et al.; Auditable Agents.

**Changes:** `eval/` (uv dependency group `eval`): AgentDojo suites wrapped as MCP servers behind Ledgerline; baseline vs Ledgerline runs with pinned models/seeds (utility, utility under attack, ASR); MCPTox runner; published eval policies. `tests/incidents/` (Deadbugz rug pull, postmark silent BCC with `demo-fake-mail`, GitHub toxic flow, Supabase token theft). `tests/tamper/` (agent with shell tries to delete/spoof its trace; external ledger + witness catch it). `docs/eval-report.md`, `docs/auditability-card.md`.
**What's new:** reproducible security claims ("under these benchmarks") and a permanent incident regression suite.
**Test:** incident + tamper suites in CI; benchmark eval manual/nightly (token budget). Tag v0.0.11.

---

## Phase 11 — Performance & gateway adapter (Weeks 20–21)

**Read:** DDIA stream processing; *Building Secure and Reliable Systems* (recovery); Envoy `ext_authz`; agentgateway / ContextForge (Python) plugin docs.

**Changes:** `demo-echo` server baseline; `load/locustfile.py` scenarios; `py-spy`/`cProfile` profiling and fixes (uvloop, batched commits, connection pooling); `src/ledgerline/extauthz/` gRPC ext_authz service + `ledgerline extauthz`; `deploy/agentgateway/` compose example; optional ContextForge plugin; optional outbox → NATS only if measured need; `docs/load-report.md`.
**What's new:** Ledgerline plugs into existing gateways; overhead measured and published.
**Test:** targets from the Stack section; adapter integration test in compose. Tag v0.0.12.

---

## Phase 12 — Schema spec, independent verifier & upstream (Week 22)

**Read:** IETF agent-audit-trail draft (latest); Agent Receipts spec; OTel semconv contribution guide.

**Changes:** `spec/ledgerline-event-v0.1.md` (normative: fields, canonicalisation, hashing, checkpoint format, verification algorithm); frozen `schema/event.schema.json` v0.1; `spec/vectors/*.json` conformance vectors (valid/tampered chains, proofs, checkpoints, expected results); `verifiers/reference/` — an **independent clean-room verifier** sharing no code with `src/ledgerline` (the Merkle layer is already cross-checked: Go `tlogd` builds it, Python verifies it); `spec/mappings/{otel-genai,agent-receipts,ietf-agent-audit-trail}.md`; CI runs both verifiers against all vectors.
**What's new:** a documented, testable format any implementation can verify. Exit: upstream issue/PR opened. Tag v0.0.13.

---

## Phase 13 — Open-source launch v0.1.0 (Weeks 23–24)

**Read:** OpenSSF Scorecard checks; opensource.guide; PyPI trusted publishing; Sigstore Python; SLSA levels.

**Changes:** README (honest positioning, diagram, quickstart, headline eval/load numbers); MkDocs Material site (concepts, quickstart, policy guide, spec, ADR index, FAQ vs Pipelock/agentgateway); `demos/quickstart.sh` (`docker compose up` + Supabase scenario in < 5 min); CONTRIBUTING (DCO), CODE_OF_CONDUCT, SECURITY, GOVERNANCE, MAINTAINERS; issue/PR templates, Dependabot; release workflow (PyPI trusted publishing, Sigstore-signed artifacts, CycloneDX SBOM, container image); CodeQL + Scorecard workflows; CHANGELOG v0.1.0; launch essay.
**What's new:** public, signed, documented v0.1.0. **Test:** fresh-machine quickstart < 5 min; signatures verify; Scorecard ≥ 7. **Exit:** repo public, tag v0.1.0, essay, HN post 17:30–22:30 IST.

---

## Verification (end-to-end, from Phase 7 onward)

1. `docker compose -f deploy/docker-compose.yml up -d` (Postgres, Temporal, Collector/Jaeger, `tlogd`, witness).
2. `make ci` (ruff, mypy strict, pytest incl. hypothesis + testcontainers).
3. `demos/supabase.sh`: allowed ticket read → taint → hijacked query → `needs_approval` → deny → agent gets `isError`.
4. `ledgerline verify --run <id>` passes; `export` + `verify --offline` passes; superuser UPDATE → verify fails at that seq.
5. Playwright e2e and incident corpus pass; Jaeger trace ID equals ledger `trace_id`.
