"""The ledger entry, version 0.1: the public format (``schema/event.schema.json`` is generated from it).

Every entry has every field, with ``null`` where a value doesn't apply yet, so
the bytes that get hashed never depend on which fields a writer chose to omit.

Two kinds of entry share one chain:

- ``request``: a ``tools/call`` and Ledgerline's decision about it, written
  *before* the call is forwarded (or refused).
- ``outcome``: what came back, linked to its request by ``outcome.request_hash``.

Regenerate the JSON Schema after changing a model: ``make event-schema``.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.1"
HEX64 = r"^[0-9a-f]{64}$"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Actor(_Strict):
    user: str | None = Field(description="The person the agent acts for, if known.")
    agent: str | None = Field(description="The MCP client, e.g. 'claude-code 2.1.0', from its clientInfo.")
    on_behalf_of_chain: list[str] = Field(
        description="Who delegated to whom, outermost first (user, then agent). Phase 10 extends it."
    )


class DecisionRecord(_Strict):
    effect: Literal["allow", "deny"]
    control: str | None = Field(description="Which control decided, e.g. 'verify-before-call'.")
    reason: str | None


class OutcomeRecord(_Strict):
    status: Literal["ok", "tool_error", "error"] = Field(
        description="'tool_error': the tool answered isError; 'error': a JSON-RPC error."
    )
    result_digest: str | None = Field(description="HMAC-SHA256 of the result (or error), like args_digest.")
    request_hash: str = Field(pattern=HEX64, description="entry_hash of the request this answers.")


class Entry(_Strict):
    schema_version: Literal["0.1"]
    seq: int = Field(ge=1, description="Position in the run's chain, from 1, with no gaps.")
    ts: str = Field(description="When it was written, RFC 3339 UTC with milliseconds.")
    run_id: str = Field(description="The chain this entry belongs to (one proxy session).")
    tenant: str
    kind: Literal["request", "outcome"]
    actor: Actor
    protocol: Literal["mcp"]
    method: str
    server: str = Field(description="Which server: its command line or URL.")
    tool: str | None
    tool_def_sha256: str | None = Field(
        description="The pinned (approved) definition's RFC 8785 SHA-256, if the tool is pinned."
    )
    args_digest: str | None = Field(
        description="HMAC-SHA256 (tenant key) over the RFC 8785 form of the arguments (ADR-008)."
    )
    session_taint: str | None = Field(description="Reserved for Phase 5.")
    decision: DecisionRecord | None = Field(description="Set on request entries.")
    outcome: OutcomeRecord | None = Field(description="Set on outcome entries.")
    trace_id: str | None = Field(description="Reserved for Phase 7 (OpenTelemetry).")
    prev_hash: str = Field(pattern=HEX64, description="entry_hash of the previous entry; 64 zeros first.")
    entry_hash: str = Field(
        pattern=HEX64, description="SHA-256 of the RFC 8785 form of this entry without entry_hash."
    )


def json_schema() -> str:
    schema = Entry.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://github.com/pun33t19/ledgerline/schema/event.schema.json"
    schema["title"] = f"Ledgerline ledger entry v{SCHEMA_VERSION}"
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    print(json_schema(), end="")
