# MCP wire fixtures

Raw JSON-RPC traffic between `demo-client` and each demo server over stdio, captured with `internal/wiretap`. Each line is `{"dir": "sent"|"received", "msg": <JSON-RPC message>}` from the client's point of view.

Regenerate with `make fixtures`. The capture is deterministic; CI fails if a regeneration produces a diff.

| File | Scenario |
|---|---|
| `weather-stdio.jsonl` | Honest server: discover → list → one `get_weather` call |
| `poisoned-stdio.jsonl` | Tool-poisoning server: the `add` description hides instructions; the call carries the "stolen" fake secret in `sidenote` |
| `rugpull-stdio.jsonl` | Four calls; the tool description changes after call 3. No `list_changed` notification appears, because the client didn't subscribe. Only re-listing reveals the change |

**Caveat.** `wiretap` records messages after the SDK decodes them and re-encodes them, not the raw bytes read from the pipe. Both ends use the same SDK encoder, so the two match today. Phase 2's byte-identical relay test must still capture raw bytes at the proxy rather than trust this.
