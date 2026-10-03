# Prior art

What already exists close to Ledgerline, and what that leaves for us to build. Re-check this file before any public comparison (README, launch post, talks). Projects move fast.

**Method.** "Checked" means the project's own README, docs or spec page was read on the date shown. That is shallower than reading the code. Anything not checked is copied from the deep-dive research notes and marked *unverified*.

## Summary

| Project | Kind | Lang / licence | Hash chain | Signatures | Merkle proofs / witnesses | Delegation lineage | Policy decision + approval in record | Status |
|---|---|---|---|---|---|---|---|---|
| **Pipelock** | Agent firewall (HTTP, MCP stdio+HTTP, A2A, WebSocket) | Go; Apache-2.0 core, ELv2 multi-agent features | Yes, JSONL | Ed25519 receipts + signed checkpoints | Checkpoints can be anchored to Rekor; README says the "operator-independence path is still being proven". No inclusion/consistency proofs described | Not described | Receipt carries verdict + **policy hash**; HITL approval exists | Checked 2026-09-30 |
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

## What this changes for Ledgerline

1. **Hash chain + Ed25519 + verifier is table stakes.** Pipelock, Agent Receipts and Aileron all ship it. We don't claim novelty there.
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
