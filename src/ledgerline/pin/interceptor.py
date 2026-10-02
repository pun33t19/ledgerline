"""The interceptor that enforces tool pins.

Two rules, both built on the Phase 1 findings:

1. **Every ``tools/list`` reply is checked.** Tools whose definition no longer
   matches the pin (or that were never pinned) are removed from the reply,
   so the model never reads a changed, possibly poisoned, description.

2. **Every ``tools/call`` is checked before it is forwarded.** By default the
   proxy asks the server for the tool's *current* definition right before
   forwarding the call. Hosts may never re-list tools and servers needn't
   announce changes, so waiting for a listing isn't enough: a server that
   changes mid-session (the Deadbugz pattern) is caught on the very next call.

With ``tofu`` ("trust on first use"), tools not yet in the lock file are
pinned the first time they are seen instead of being refused. That's
convenient for demos but weaker: a server that is malicious from the start
gets pinned too.
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ledgerline.jsonrpc import INVALID_PARAMS, JSON, Message, envelope, error_response, tool_error_result
from ledgerline.pin.canonical import NotCanonicalizable, sha256_hex
from ledgerline.pin.lockfile import Lockfile, PinnedTool
from ledgerline.proxy.interceptor import (
    FORWARD,
    Block,
    Decision,
    Interceptor,
    Replace,
    Upstream,
    UpstreamError,
)

log = logging.getLogger("ledgerline.pin")

Alert = Callable[[JSON], None]

# Safety valve when following tools/list pagination on the server.
MAX_LIST_PAGES = 100


class PinInterceptor(Interceptor):
    def __init__(
        self,
        lock: Lockfile,
        *,
        lock_path: Path | None = None,
        tofu: bool = False,
        verify_each_call: bool = True,
        on_alert: Alert | None = None,
    ) -> None:
        self.lock = lock
        self.lock_path = lock_path
        self.tofu = tofu
        self.verify_each_call = verify_each_call
        self.on_alert = on_alert or (lambda _event: None)
        # Latest hash the server sent for each tool, from any listing.
        self.observed: dict[str, str] = {}

    # --- tools/list replies -------------------------------------------------

    async def on_response(self, request: Message, response: Message) -> Decision:
        if request.method != "tools/list" or response.result is None:
            return FORWARD
        tools = response.result.get("tools")
        if not isinstance(tools, list):
            return FORWARD

        kept = [tool for tool in tools if self._check_listed(tool)]
        if len(kept) == len(tools):
            return FORWARD  # nothing removed: forward the original bytes
        body = copy.deepcopy(response.body)
        body["result"]["tools"] = kept
        return Replace(body)

    def _check_listed(self, tool: Any) -> bool:
        """True if this listed tool may be shown to the client."""
        if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
            self._alert("malformed_tool", None, detail="tools/list entry without a string name")
            return False
        name: str = tool["name"]
        try:
            sha = sha256_hex(tool)
        except NotCanonicalizable as e:
            self._alert("unhashable_tool", name, detail=str(e))
            return False
        self.observed[name] = sha
        return self._accept(name, tool, sha)

    def _accept(self, name: str, definition: JSON, sha: str) -> bool:
        pinned = self.lock.tools.get(name)
        if pinned is None:
            if self.tofu:
                self._pin(name, definition)
                return True
            self._alert("unpinned_tool", name, actual=sha)
            return False
        if pinned.sha256 != sha:
            self._alert("tool_changed", name, expected=pinned.sha256, actual=sha)
            return False
        return True

    def _pin(self, name: str, definition: JSON) -> None:
        self.lock.tools[name] = PinnedTool.of(definition)
        log.warning("pinned new tool %r on first use (sha256 %s)", name, self.lock.tools[name].sha256[:12])
        if self.lock_path is not None:
            self.lock.save(self.lock_path)

    # --- tools/call requests ------------------------------------------------

    async def on_request(self, request: Message, upstream: Upstream) -> Decision:
        if request.method != "tools/call":
            return FORWARD
        name = request.params.get("name")
        if not isinstance(name, str):
            return Block(
                error_response(request.id, INVALID_PARAMS, "tools/call needs a string name"), "bad_params"
            )

        if self.verify_each_call:
            try:
                current = await self._fetch_definition(name, request, upstream)
            except UpstreamError as e:
                # Fail closed: if we can't confirm the definition, don't run the tool.
                return self._block(
                    request, name, "verify_failed", f"could not verify the tool definition ({e})"
                )
            if current is None:
                return self._block(request, name, "tool_missing", "the server no longer lists this tool")
            try:
                sha = sha256_hex(current)
            except NotCanonicalizable as e:
                return self._block(request, name, "unhashable_tool", str(e))
            self.observed[name] = sha
            if not self._accept(name, current, sha):
                return self._blocked_for_pin(request, name, sha)
            return FORWARD

        # Without per-call verification, rely on the latest listing we saw.
        sha_seen = self.observed.get(name)
        pinned = self.lock.tools.get(name)
        if pinned is None and not self.tofu:
            return self._blocked_for_pin(request, name, sha_seen)
        if pinned is not None and sha_seen is not None and sha_seen != pinned.sha256:
            return self._blocked_for_pin(request, name, sha_seen)
        return FORWARD

    async def _fetch_definition(self, name: str, request: Message, upstream: Upstream) -> JSON | None:
        """Ask the server for ``name``'s current definition, following pagination."""
        params: JSON = {}
        if meta := envelope(request):
            params["_meta"] = meta
        for _ in range(MAX_LIST_PAGES):
            result = await upstream.request("tools/list", params, like=request)
            for tool in result.get("tools") or []:
                if isinstance(tool, dict) and tool.get("name") == name:
                    return tool
            cursor = result.get("nextCursor")
            if not isinstance(cursor, str):
                return None
            params = {**params, "cursor": cursor}
        raise UpstreamError(f"tools/list did not finish within {MAX_LIST_PAGES} pages")

    def _blocked_for_pin(self, request: Message, name: str, sha: str | None) -> Block:
        pinned = self.lock.tools.get(name)
        if pinned is None:
            return self._block(
                request, name, "unpinned_tool", "the tool is not pinned; review it and run `ledgerline pin`"
            )
        got = f"{sha[:12]}…" if sha else "unknown"
        return self._block(
            request,
            name,
            "tool_changed",
            f"its definition changed since it was pinned (pinned sha256 {pinned.sha256[:12]}…, now {got}). "
            "Review the new definition and re-run `ledgerline pin` to accept it",
        )

    def _block(self, request: Message, name: str, event: str, why: str) -> Block:
        self._alert(f"call_blocked:{event}", name)
        text = f"Blocked by Ledgerline: tool {name!r} was not called because {why}."
        return Block(tool_error_result(request, text), event)

    def _alert(self, event: str, tool: str | None, **details: Any) -> None:
        payload: JSON = {"event": event, "tool": tool, **details}
        shown = {
            k: (f"{v[:12]}…" if k in ("expected", "actual") and isinstance(v, str) else v)
            for k, v in details.items()
        }
        log.warning("%s: tool %r %s", event, tool, " ".join(f"{k}={v}" for k, v in shown.items()))
        self.on_alert(payload)
