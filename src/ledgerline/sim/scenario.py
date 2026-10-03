"""What a scenario is: a malicious server, a scripted agent's steps, and the expected outcomes."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ledgerline.sim.events import Verdict


@dataclass(frozen=True)
class Discover:
    """The 2026-07-28 handshake: ``server/discover``."""


@dataclass(frozen=True)
class ListTools:
    """Ask for the tool menu (what a host does when it starts or refreshes)."""


@dataclass(frozen=True)
class CallTool:
    """Call a tool. The agent fills in anything the tool's description asks for (it obeys).

    ``only_if_listed``: a careful host only calls tools in its *latest* menu;
    a host that never refreshes keeps calling tools from its old menu.
    """

    name: str
    args: dict[str, object] = field(default_factory=dict)
    only_if_listed: bool = False


@dataclass(frozen=True)
class ObeyNewInstructions:
    """Call any listed tool whose description tells the model to call it (a hijacked model would)."""


@dataclass(frozen=True)
class SendRaw:
    """Send hand-crafted bytes: an attacker or buggy plugin on the wire, not the model."""

    title: str
    build: Callable[[str], bytes]  # gets the fake secret, returns one JSON-RPC line (without newline)
    msg_id: int


AgentStep = Discover | ListTools | CallTool | ObeyNewInstructions | SendRaw


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    category: str
    difficulty: str  # easy | medium | hard
    summary: str
    story: str  # what happens, in plain language
    server: Callable[[Path], list[str]]  # exfil log path -> server command
    steps: tuple[AgentStep, ...]
    expected_unprotected: Verdict
    expected_protected: Verdict
    controls_that_matter: tuple[str, ...] = ()
    incident: str = ""
    owasp_mcp: tuple[str, ...] = ()
    owasp_asi: tuple[str, ...] = ()
    honest_note: str = ""


def demo_server(module: str, *args: str) -> Callable[[Path], list[str]]:
    """Command for a demo server module, run with this Python so it works from any install."""

    def command(exfil_log: Path) -> list[str]:
        return [
            sys.executable,
            "-m",
            f"ledgerline.demo.servers.{module}",
            *args,
            "--exfil-log",
            str(exfil_log),
        ]

    return command
