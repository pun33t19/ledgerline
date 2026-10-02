# MCP wire fixtures

JSON-RPC traffic between `demo-client` and each demo server over stdio, captured with `ledgerline.wiretap`. Each line is `{"dir": "sent"|"received", "msg": <JSON-RPC message>}` from the client's point of view.

Regenerate with `make fixtures`. The capture is deterministic; CI fails if a regeneration produces a diff.

| File | Scenario |
|---|---|
| `weather-stdio.jsonl` | Honest server, 2026-07-28: `server/discover` → list → one `get_weather` call → list |
| `weather-stdio-legacy.jsonl` | The same with `--legacy`: `initialize` → `notifications/initialized` → … (protocol 2025-11-25) |
| `poisoned-stdio.jsonl` | Tool-poisoning server: the `add` description hides instructions; the call carries the "stolen" fake secret in `sidenote` |
| `rugpull-stdio.jsonl` | Four calls; the description changes after call 3. No `list_changed` notification appears, because the client didn't subscribe. Only re-listing reveals the change |

**Caveat.** `wiretap` records messages as the SDK's pydantic models serialise them (`model_dump(by_alias=True, exclude_unset=True)`, the same options its stdio transport uses), not the raw bytes read from the pipe. Phase 2's relay test must capture raw bytes at the proxy rather than trust this.
