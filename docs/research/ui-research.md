# UI research: making Ledgerline's interface its main face

*Research date: 2026-10-03. Sources are listed at the end; vendor claims are marked [vendor].*

## 1. Question

Ledgerline's value (deterministic control of agent actions, plus verifiable evidence) is invisible on the command line. How should the UI present it, starting with an **attack simulation lab**, and what else belongs in the UI?

## 2. What exists today

| Tool | What its UI does well | What it lacks for our purpose |
|---|---|---|
| **Promptfoo** (red teaming; acquired by OpenAI in 2025) | Web dashboard of attack results mapped to OWASP, NIST, MITRE; has an MCP plugin for tool-calling vulnerabilities [vendor] | Reports pass/fail per probe. Doesn't show the *mechanics* of an attack or which control stopped it |
| **PyRIT** (Microsoft), **garak** (NVIDIA) | Rich attack libraries, probes and detectors | Python- or CLI-first; little or no interactive UI |
| **Damn Vulnerable MCP Server (DVMCP)** | 10 progressive MCP challenges (tool poisoning, rug pull, shadowing, indirect injection, token theft, multi-vector…), MIT licensed | Runs in Docker and is driven through an MCP client. **No visual UI**; you can't see the attack flow |
| **Lakera Gandalf / Agent Breaker** | Gamified levels; very effective teaching | About prompt-level defences; no tool or protocol layer, no evidence |
| **MCP-Scan** (Invariant/Snyk) | Scans tool descriptions; proxy mode for live monitoring | Detection-oriented; no side-by-side "with vs without defence" story |
| **MCP Replay, MCPcat session replay** | Two-panel timeline + detail view of every request and response | Debugging only; no security decisions or verification |
| **MCP Dandan** | Real-time dashboard, interactive tutorial, blocking interface | LLM-based detection (heuristic); no evidence layer |
| **HOL "static lab" (MCP tool poisoning)** | Shows a fake tool description and a simulated trace with a guard flagging it | Static teaching page; not a running system |
| **Rekor / CT tooling, Merkle visualizers** | Inclusion-proof viewers; tree visualizations | Generic; not tied to agent actions |
| **Temporal UI** | Workflow history and pending signals | Generic workflow engine view, not an approval product |

**Gap:** no tool shows the *same* agent attack run **unprotected and protected side by side**, animates the protocol messages, says **exactly which control** intervened, maps it to OWASP/MITRE, and then lets you **verify the evidence**. That combination is Ledgerline's UI identity.

## 3. Design principles drawn from the research

1. **Show mechanics, not just verdicts.** Animate the actual JSON-RPC messages (host → Ledgerline → server) and let the user click any message to read it raw. Teaching labs succeed when you *watch* the attack happen (Gandalf, DVMCP).
2. **Contrast is the story.** Every scenario runs twice, without and with Ledgerline, in a split screen with a clear outcome ("attacker received `FAKE_API_KEY…`" vs "blocked at call 4 by *pin check*").
3. **Two-panel timeline + detail** (the session-replay pattern): events on the left; full raw message, decision and reason on the right.
4. **Evidence first, verdict last** in approvals: action requested → evidence (failed or missing checks shown as explicit ✗ rows) → the agent's own verdict collapsed by default → actions. This avoids anchoring reviewers on the model's conclusion.
5. **Model's-eye vs user's-eye view.** Show what a host UI displays for a tool (often only the first line) next to what the model actually reads. This makes tool poisoning obvious.
6. **Map everything to frameworks** (OWASP MCP Top 10, OWASP Agentic Top 10 ASI, MITRE ATLAS) with a **coverage heatmap**, the way security teams already think (ATLAS Navigator, Promptfoo reports).
7. **Make tampering visible.** Hash chains and Merkle proofs only convince when you can edit a record and watch verification fail at exactly that link.
8. **Honest limits on screen.** When a control does *not* stop a scenario (e.g. a server poisoned from day one gets pinned as-is), the UI says so and names the phase that will.
9. **Deterministic by default, live model optional.** Scripted "hijacked model" runs are reproducible and free; a later "real model" mode shows whether an actual LLM obeys, with a cost guard.
10. **The UI is a security boundary too.** Local web UIs are a known attack path (the MCP Inspector RCE was an unauthenticated local proxy). Bind to 127.0.0.1, require a startup token, and validate `Origin`/`Host`.

## 4. Feature catalogue

ID, feature, and the phase that ships it (phase numbers follow the updated roadmap).

### Attack Simulation Lab
| ID | Feature | Phase |
|---|---|---|
| UI-01 | **Scenario catalogue**: cards per attack (category, difficulty, OWASP/ATLAS tags, real incident it mirrors) | 3 |
| UI-02 | **Split-screen run**: the same scenario unprotected vs protected, with outcome banners | 3 |
| UI-03 | **Animated message flow** (React Flow): host → Ledgerline → server, colour-coded by decision; click a message to inspect raw JSON | 3 |
| UI-04 | **Timeline + inspector** (two-panel): step, pause, replay; raw JSON, decision, reason, matched control | 3 |
| UI-05 | **Defence toggles**: switch individual controls (pinning, per-call verification, strict parsing, header checks) and re-run to see which control stops what | 3 |
| UI-06 | **Model's-eye vs user's-eye** view of tool descriptions | 3 |
| UI-07 | **Tool diff viewer**: pinned vs current definition, highlighted additions such as `<IMPORTANT>` blocks; approve or reject (UI version of `ledgerline pin`) | 3 |
| UI-08 | **Coverage heatmap**: scenarios × controls, and OWASP MCP / ASI / ATLAS coverage, from the latest runs | 3 (grows every phase) |
| UI-09 | **Attack kill-chain strip**: recon → poison → trigger → exfiltrate, with where Ledgerline intervened | 3 |
| UI-10 | **Scenario builder**: compose a custom attack (server behaviour, description template, trigger after N calls, payload) and save it as a regression case | 5 |
| UI-11 | **Incident replays**: narrated reproductions of Supabase token theft, postmark BCC, GitHub toxic flow, Deadbugz | 5–6 |
| UI-12 | **Live-model mode**: run a scenario against a real LLM (Claude via API) and watch whether it obeys; shows the transcript; cost estimate and cap | 11 |
| UI-13 | **Challenge mode** (Gandalf-style): try to get an attack past Ledgerline's policies; local leaderboard | 11 |
| UI-14 | **Report export**: a run or campaign as a shareable HTML/PDF evidence report | 8 |

### Evidence and verification
| ID | Feature | Phase |
|---|---|---|
| UI-15 | **Ledger explorer**: per-run timeline of ledger entries | 4 |
| UI-16 | **Hash-chain visualizer + tamper demo**: edit a stored entry and watch verification turn red at the broken link | 4 |
| UI-17 | **One-click verify** with an animated step-by-step check | 4 |
| UI-18 | **Merkle tree visualizer**: inclusion-proof path highlighted, consistency proof between two checkpoints | 9 |
| UI-19 | **Witness and checkpoint status**: cosigners, checkpoint lag | 9 |
| UI-20 | **Drag-and-drop offline verifier**: drop an exported bundle; verified *in the browser* by an independent TypeScript implementation | 9 (feeds the Phase 13 independent verifier) |

### Policy and control
| ID | Feature | Phase |
|---|---|---|
| UI-21 | **Policy studio**: Cedar editor (Monaco, syntax highlighting), test cases, run tests | 5 |
| UI-22 | **What-if evaluator**: principal + tool + args + taint → decision and matched rule | 5 |
| UI-23 | **Taint visualizer**: session badge and *which* content tainted it | 5 |
| UI-24 | **Policy change review**: diff between bundles, flags rules that widen permissions | 5 |
| UI-25 | **Pinned-server registry**: servers, pinned tools, last verification, re-pin flow | 3 (basic) → 8 |

### Human oversight
| ID | Feature | Phase |
|---|---|---|
| UI-26 | **Approval inbox, evidence-first cards**: action → evidence (✗ rows for failed checks) → collapsed agent verdict → approve/deny; timeout countdown; keyboard shortcuts | 6 |
| UI-27 | **Approval history** with links to ledger entries | 6 |

### Operations and multi-agent
| ID | Feature | Phase |
|---|---|---|
| UI-28 | **Live traffic monitor**: calls per second, blocks, alerts feed, added latency; links to traces | 7 |
| UI-29 | **Delegation graph**: user → agents → tools, identity-loss highlighted | 10 |
| UI-30 | **Benchmark dashboard**: AgentDojo/MCPTox utility vs attack success rate, compared with published defences | 11 |
| UI-31 | **Performance dashboard**: added latency p50/p95/p99, throughput | 12 |
| UI-32 | **Schema explorer**: the event spec, field docs and examples | 13 |
| UI-33 | **Public hosted demo** (read-only lab with recorded runs) | 14 |

### Cross-cutting
| ID | Feature | Phase |
|---|---|---|
| UI-34 | App shell: navigation, dark/light theme, keyboard navigation, accessible colour pairs | 3 → 8 |
| UI-35 | Guided tours and glossary pop-overs (beginner mode) | 3 → 8 |
| UI-36 | UI security: 127.0.0.1 binding, startup token, `Origin`/`Host` checks, CSP; OIDC login for shared deployments | 3 → 8 |

## 5. Technology choice

Decided: **React + TypeScript frontend** with the Python backend unchanged (ADR-005). Libraries (current versions checked on npm):

| Need | Choice |
|---|---|
| Build / dev server | Vite 8 |
| Framework | React 19 + TypeScript (strict) |
| Styling / components | Tailwind CSS 4 + Radix primitives (shadcn/ui pattern) |
| Graphs and animated flows | React Flow (`@xyflow/react` 12) |
| Animation | Motion |
| Charts | Recharts 3 |
| Server data | TanStack Query 5 |
| Editors / diffs | Monaco (`@monaco-editor/react`) |
| Routing | React Router |
| API types | `openapi-typescript`, generated from FastAPI's OpenAPI schema so Python stays the source of truth |
| Tests | Vitest + Testing Library; Playwright for end-to-end |
| Lint / format | Biome |

**Live updates:** FastAPI WebSocket per run, streaming typed events (message, decision, alert, exfiltration, outcome).

## 6. Simulation engine (backend)

- **Scenarios** are typed Python definitions: id, title, category, framework tags, the incident they mirror, server command, scripted agent steps, expected unprotected and protected outcomes.
- **Scripted "hijacked model"**: the runner plays an agent that obeys whatever the tool descriptions say (reads the fake secret, fills the smuggling field). It's deterministic, free, and works in CI.
- **Runner** executes a scenario in two modes. *Unprotected* connects straight to the server. *Protected* runs it through the real `StdioProxy` with the chosen controls. It emits events from an `EventSink` interceptor plus the attacker's exfiltration log.
- **Scenario outcomes are tests.** Every scenario is also a pytest case asserting both expected outcomes, so the lab doubles as the security regression suite.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Second language (TypeScript) to learn | A small, typed API surface; generated types; the guide explains React for Java developers |
| UI scope creep delays the core | Each phase ships a *thin* UI slice tied to that phase's backend; polish lands in Phase 8 |
| A local web UI becomes an attack path | UI-36 controls in Phase 3, before anything else is exposed |
| Simulations that look staged | Scripted mode is labelled as such; live-model mode (UI-12) shows real behaviour |

## Sources

- Promptfoo vs PyRIT / garak: https://www.promptfoo.dev/blog/promptfoo-vs-pyrit/ · https://www.promptfoo.dev/blog/promptfoo-vs-garak/ · https://www.giskard.ai/knowledge/promptfoo-alternatives-ai-red-teaming
- Damn Vulnerable MCP Server: https://github.com/harishsg993010/damn-vulnerable-MCP-server
- Lakera Gandalf / CTF overview: https://bishopfox.com/blog/ready-to-hack-an-llm-our-top-ctf-recommendations
- MCP-Scan: https://explorer.invariantlabs.ai/docs/mcp-scan
- MCP tool-poisoning static lab: https://hol.org/guard/security/labs/mcp-tool-poisoning
- MCP Replay: https://mwm.ai/apps/mcp-replay/6791677666 · MCPcat session replay: https://docs.mcpcat.io/features/session-replay
- MCP Dandan: https://glama.ai/mcp/servers/@seungwon9201/MCP-Dandan
- Evidence-first approval cards: https://dev.to/haaaaaley/show-the-agents-evidence-before-asking-for-one-click-approval-1g7d
- HITL approval interfaces: https://www.gravitee.io/corpus/gen-1980/human-computer-interaction/human-in-the-loop-approval-interfaces-for-ai-agent-actions.html
- OWASP MCP Top 10: https://owasp.org/www-project-mcp-top-10/ · https://cycode.com/blog/owasp-mcp-top-10/
- MITRE ATLAS and agentic gaps: https://labs.cloudsecurityalliance.org/research/csa-research-note-atlas-agentic-gap-analysis-20260327/ · https://vectra.ai/topics/mitre-atlas
- Merkle visualizer: https://merkle-tree.utils.com/
- Reflex / NiceGUI (alternatives considered): https://reflex.dev/docs/getting-started/how-reflex-works/ · https://www.bitdoze.com/streamlit-vs-nicegui
