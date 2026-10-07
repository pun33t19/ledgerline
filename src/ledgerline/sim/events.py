"""Typed events a simulation run produces. The UI's TypeScript types are generated from these."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from ledgerline.ledger.schema import Entry

Mode = Literal["unprotected", "protected"]
Node = Literal["host", "ledgerline", "server"]
Verdict = Literal["harmed", "safe"]


class Controls(BaseModel):
    """Which Ledgerline controls are switched on for the protected run."""

    pinning: bool = True
    verify_each_call: bool = True
    strict_parsing: bool = True


class ToolDef(BaseModel):
    name: str
    description: str
    sha256: str
    definition: dict[str, Any]


class _Event(BaseModel):
    seq: int = 0
    t_ms: int = 0


class RunStarted(_Event):
    type: Literal["run_started"] = "run_started"
    run_id: str
    scenario_id: str
    controls: Controls


class Pinned(_Event):
    """The tool definitions a person approved before the protected run (via `ledgerline pin`)."""

    type: Literal["pinned"] = "pinned"
    tools: list[ToolDef]


class Step(_Event):
    type: Literal["step"] = "step"
    mode: Mode
    index: int
    title: str
    status: Literal["done", "skipped", "error"] = "done"
    detail: str = ""


class MessageEvent(_Event):
    type: Literal["message"] = "message"
    mode: Mode
    source: Node
    target: Node
    internal: bool = False
    kind: Literal["request", "notification", "response", "invalid"]
    method: str | None = None
    msg_id: str | int | None = None
    summary: str
    body: Any = None


class Decision(_Event):
    type: Literal["decision"] = "decision"
    mode: Mode
    action: Literal["blocked", "replaced", "rejected"]
    control: str
    reason: str
    method: str | None = None


class Alert(_Event):
    type: Literal["alert"] = "alert"
    mode: Mode
    event: str
    tool: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class Menu(_Event):
    """The tool list the agent can see after a listing (what the model reads)."""

    type: Literal["menu"] = "menu"
    mode: Mode
    step: int
    tools: list[ToolDef]


class Exfiltration(_Event):
    type: Literal["exfiltration"] = "exfiltration"
    mode: Mode
    via: str
    data: str


class Outcome(_Event):
    type: Literal["outcome"] = "outcome"
    mode: Mode
    verdict: Verdict
    headline: str
    stopped_by: list[str] = Field(default_factory=list)


class LedgerEntry(_Event):
    """An entry the protected side's ledger wrote (before the call it records was forwarded)."""

    type: Literal["ledger_entry"] = "ledger_entry"
    mode: Mode
    entry: Entry


class RunFinished(_Event):
    type: Literal["run_finished"] = "run_finished"
    status: Literal["finished", "failed"]
    error: str | None = None


RunEvent = Annotated[
    RunStarted
    | Pinned
    | Step
    | MessageEvent
    | Decision
    | Alert
    | Menu
    | Exfiltration
    | Outcome
    | LedgerEntry
    | RunFinished,
    Field(discriminator="type"),
]
