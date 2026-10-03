# ADR-001: Ledgerline is an evidence layer, not a gateway

- **Status:** accepted
- **Date:** 2026-09-30
- **Phase:** 0

## Context

Agents act through tools (MCP) and other agents (A2A). Those actions need least-privilege checks, human approval for risky calls, and a record that an auditor can verify without trusting the operator.

Mature open-source gateways already route, authenticate and authorise MCP/A2A traffic: agentgateway (Linux Foundation, CEL RBAC), ToolHive (argument-level Cedar), IBM ContextForge. Signed, hash-chained agent logs also exist: Pipelock, Agent Receipts, Aileron. See [prior-art.md](../prior-art.md).

What we found missing: a witnessed Merkle transparency log with offline proofs, a single record binding the policy decision *and* the human approval to the action, delegation lineage joining MCP calls to A2A hops, and a neutral schema aligned with the IETF agent-audit-trail draft and Agent Receipts.

## Decision

Ledgerline is a **gateway-neutral evidence layer** for agent actions. It:

1. Records every mediated action, policy decision, approval and delegation hop in a tamper-evident log with signed, witnessed checkpoints and an offline verifier.
2. Enforces policy and human approval at the tool boundary, because a record of a decision is only meaningful if the decision was actually enforced.
3. Ships its own small proxy (stdio + Streamable HTTP) so it can be used standalone and demoed, but treats **adapters for existing gateways** (ext-authz, plugins, event sinks) as the primary deployment path.

It will not compete on routing, load balancing, LLM provider proxying, content moderation, rate limiting or registry features.

## Consequences

- Scope stays small enough for one engineer over ~24 weeks.
- Value depends on adoption by gateways and on the schema being accepted upstream, so adapters (Phase 12) and the spec (Phase 13) are first-class deliverables, not extras.
- Our own proxy must stay minimal. Feature requests that belong in a gateway get redirected to one.
- Public claims must stay precise: never "first tamper-evident agent firewall".

## Alternatives considered

- **Build a full MCP/A2A gateway.** Duplicates agentgateway and ContextForge, and we'd lose on features.
- **Only a log format/spec, no enforcement.** Can't demonstrate pre-execution recording or approval provenance, and specs without implementations rarely get adopted.
- **Contribute directly to Pipelock.** Worth revisiting. Its ELv2 multi-agent tier and different design goals (DLP/scanning firewall) make it a poor home for a neutral evidence layer today.
