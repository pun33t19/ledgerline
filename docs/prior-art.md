# Prior art

What already exists close to Ledgerline, and what that leaves for us to build. Re-check this file before any public comparison (README, launch post, talks). Projects move fast.

**Method.** "Checked" means the project's own README, docs or spec page was read on the date shown. That is shallower than reading the code. Anything not checked is copied from the deep-dive research notes and marked *unverified*.

## Summary

| Project | Kind | Lang / licence | Hash chain | Signatures | Merkle proofs / witnesses | Delegation lineage | Policy decision + approval in record | Status |
|---|---|---|---|---|---|---|---|---|
| **Pipelock** | Agent **egress firewall** (fetch/forward/WebSocket proxies, MCP stdio+HTTP proxy, A2A inspection on those paths) + OS/host containment | Go single binary; Apache-2.0 core, **ELv2** multi-agent, **paid** Pro/Enterprise dashboard | Yes: per-writer hash-chained JSONL flight recorder | Ed25519 action receipts + signed checkpoints; **four cross-language verifiers** (Go, TS, Rust, Python) + conformance corpus (incl. duplicate keys) | Receipt-chain checkpoints anchored to a local backend or **Rekor**; operator-independence path "still being proven". No own Merkle log with per-entry inclusion/consistency proofs or witness cosigning described | Actor identity in a mediation envelope (SPIFFE), A2A Agent Card drift; "not a standalone A2A proxy"; no delegation-graph reconstruction described | Receipt: verdict, **policy hash**, transport, scanner layer. HITL modes (terminal y/N/s). Taint escalation. 30 built-in tool-policy rules + 10 tool-chain patterns (pattern-based, not a policy language) | **Re-checked 2026-10-03** (full README + docs/comparison.md + playground) |
| **Agent Receipt Protocol** | Receipt format (W3C VC profile), v0.5.0 draft | Spec | Yes | Ed25519 (Ed25519Signature2020) | Not in core; points to adjacent projects using Rekor | `delegation` field with parent chain reference | Not recorded in receipts | Checked 2026-09-30 |
| **IETF draft-sharif-agent-audit-trail** | Individual I-D, **-06 (2026-09-29)**, no formal standing | Spec | Yes; RFC 8785 JCS + SHA-256, genesis `prev_hash = null` | Optional ECDSA P-256; ML-DSA-65 hybrid since -04 | Optional RFC 6962 Merkle epochs + RFC 3161 timestamps / WORM anchoring | `delegation` action type (delegate agent, trust level, task hash, constraints) | Mandates **pre-execution** records for denied/escalated decisions | Checked 2026-09-30 |
| **Aileron** | Agent flight recorder | **Python**; Apache-2.0 | Yes, genesis `0x00…00` | Ed25519 over chain-tip checkpoints (prefix commitments) | No Merkle; linear chain only | Not described | 32 YAML rules before execution; blocked calls logged | Checked 2026-09-30 |
| **agentgateway** (Linux Foundation) | MCP + A2A gateway | **Rust**; Apache-2.0; ~5.1k★ | None mentioned | — | — | — | CEL RBAC, JWT/OAuth, OTel; guardrail webhooks | Checked 2026-09-30 |
| **ToolHive** (Stacklok) | MCP server runtime/gateway | Go | — | — | — | — | Argument-level Cedar (`resource.arg_*`) and MCP annotations (`destructiveHint`…); docs **don't cover decision audit** | Checked 2026-09-30 |
| IBM ContextForge | MCP gateway/registry | Python; ~4.3k★ | ? | ? | ? | ? | Plugin system | *Unverified* |
| Trail of Bits mcp-context-protector | Tool-definition pinning | ? | — | — | — | — | Rug-pull detection | *Unverified* |
| Invariant MCP-Scan (now Snyk) | Scanner + pinning | ? | — | — | — | — | Tool pinning | *Unverified* |
| Docker MCP Gateway | Gateway | Go | ? | Image signature verification | — | — | — | *Unverified* |
| Aegis (*Auditable Agents* paper) | Research firewall | ? | Yes | Signed | ? | ? | 48/48 attacks blocked, 8.3 ms median | *Unverified* (preprint) |

## Pipelock in detail (re-checked 2026-10-03)

The 2026-09-30 check used a short README summary and **understated Pipelock**. A full read shows it already ships much of what Ledgerline planned:

- **Already in Pipelock:** mid-session rug-pull detection on `tools/list`, tool-poisoning scanning, tool policy (30 rules) and tool-call chain detection, session **taint escalation**, HITL approval modes, A2A inspection and Agent Card drift, MCP binary integrity manifests (hash pinning of server *binaries*), signed receipts with **four independent verifiers** and a conformance corpus, Rekor anchoring, an attack-simulation `assess` command, a public benchmark (agent-egress-bench), a web **playground** (protected run only, downloadable signed bundles, browser verification) and an operator **dashboard** (evidence viewer free; Overview/Agents/Budgets Pro; Fleet/Workbench/Incident Enterprise).
- **Pipelock's centre of gravity:** *egress* control. DLP (65 patterns, entropy, BIP-39), prompt-injection response scanning, SSRF and DNS checks, WebSocket and TLS interception, sandbox and host containment, a 7-source kill switch. Detection is largely **pattern and heuristic based**.
- **Not found in Pipelock's docs:** its own Merkle transparency log with per-entry inclusion and consistency proofs and external witness cosigning; an analysable, author-written **policy language** (Cedar) with decision provenance down to the matched rule and input digest; **durable** (crash-surviving) approvals with timeout-means-deny; reconstruction of delegation graphs across MCP and A2A hops; gateway-neutral adapters (ext-authz) as the primary deployment; a side-by-side **unprotected vs protected** attack lab; a fully Apache-2.0 UI.

**Consequence:** Ledgerline must not position itself as "an MCP firewall with receipts"; that's Pipelock. Its defensible position is an **authorization + evidence layer**: deterministic, analysable policy on actions, durable human oversight, a witnessed transparency log, delegation lineage, gateway neutrality, and a fully open UI that teaches and proves. It is **complementary** to Pipelock (egress/DLP/containment), and the two can run together.

## What this changes for Ledgerline

1. **Hash chain + Ed25519 + verifier is table stakes.** Pipelock, Agent Receipts and Aileron all ship it; Pipelock even has four cross-language verifiers. We don't claim novelty there.
2. **Merkle log with inclusion + consistency proofs and a witness** is still open in agent-audit OSS. Pipelock is heading towards Rekor anchoring, though, and the IETF draft specifies optional RFC 6962 epochs. Our contribution is a **working, witnessed implementation** plus an offline verifier, not the idea. Re-check Pipelock before launch.
3. **Policy-decision provenance.** Pipelock records a policy hash. The IETF draft requires pre-execution records for denials and escalations. Nobody we checked binds *engine + bundle digest + input digest + matched rule + human approver* into one signed record. That binding is ours.
4. **Delegation lineage.** Agent Receipts and the IETF draft both have delegation fields. Joining MCP calls to A2A hops under OAuth actor claims (`act`, RFC 8693) was not found anywhere.
5. **Schema convergence.** Don't invent a fourth incompatible format. Our event schema should map field-for-field onto the IETF draft and Agent Receipts (Phase 13), and use RFC 8785 JCS as they both do.

## Decisions this memo feeds

- ADR-001: evidence layer, not a gateway. The gateways (agentgateway, ToolHive, ContextForge) are mature. Adapt to them.
- Done in Phase 2 (ADR-003): RFC 8785 JCS for all hashing, as the IETF draft and Agent Receipts do.
- Phase 4: decide genesis `prev_hash` (IETF draft uses `null`, Aileron uses all-zeros). Prefer the IETF convention unless there's a reason not to.
- Phase 9: consider ECDSA P-256 alongside Ed25519 for IETF-draft compatibility.

## Open items to verify

- [ ] Pipelock source: does it compute Merkle trees or only anchor chain tips?
- [ ] ContextForge plugin API: can it host an ext-authz-style hook?
- [ ] mcp-context-protector and MCP-Scan: hash algorithm and what exactly they pin
- [ ] Aegis: is code released?
- [ ] IETF draft -06: read §4 and §6.4 in full
