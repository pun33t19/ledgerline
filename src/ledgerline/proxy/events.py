"""What the proxy reports while it works: messages per hop, decisions, alerts.

The attack simulator and the UI subscribe to these to animate each message
and show which control intervened. By default nothing listens (``ProxyEvents``
is a no-op base class), so a normal proxy pays almost nothing for it.

Hops, from the proxy's point of view::

    client ──client→proxy──► Ledgerline ──proxy→server──► server
    client ◄─proxy→client─── Ledgerline ◄─server→proxy─── server
"""

from __future__ import annotations

from typing import Literal

from ledgerline.jsonrpc import JSON, Message

Hop = Literal["client→proxy", "proxy→server", "server→proxy", "proxy→client"]
Action = Literal["blocked", "replaced", "rejected"]

# Names of the controls that can make a decision (shown in the UI).
CONTROL_PINNING = "tool-pinning"
CONTROL_VERIFY = "verify-before-call"
CONTROL_PARSING = "strict-parsing"


class ProxyEvents:
    """Base class: every hook does nothing. Override the ones you need."""

    def message(self, hop: Hop, message: Message | None, raw: bytes, *, internal: bool = False) -> None:
        """A message crossed ``hop``. ``message`` is None if it couldn't be parsed.

        ``internal`` marks the proxy's own requests to the server (e.g. checking
        a tool's current definition), which the client never sees.
        """

    def decision(self, action: Action, control: str, reason: str, message: Message | None) -> None:
        """A control stopped (``blocked``/``rejected``) or changed (``replaced``) a message."""

    def alert(self, event: JSON) -> None:
        """A control raised an alert (e.g. a tool definition changed)."""


NO_EVENTS = ProxyEvents()
