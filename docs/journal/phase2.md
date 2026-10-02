# Phase 2 journal — interceptor + tool pinning

## Reading checklist

- [ ] DDIA 2e: the log and storage chapters
- [ ] MCP spec 2026-07-28: transports (stdio framing, Streamable HTTP, SSE, `Mcp-Method`/`Mcp-Name`)
- [ ] `sparfenyuk/mcp-proxy` source (a simple Python MCP proxy, to compare designs)
- [ ] ETDI paper (signed, versioned tool definitions)
- [ ] Trail of Bits `mcp-context-protector` (another take on pinning)
- [ ] RFC 8785 (skim §3: how numbers and strings are canonicalised)
- [ ] anyio docs: task groups, subprocesses, cancellation

## Try it yourself (manual tests)

Run `make install` first.

1. **The demo:** `./demos/phase2.sh`
2. **Pin and inspect a lock file:**
   ```sh
   .venv/bin/ledgerline pin --lock /tmp/weather.lock -- .venv/bin/demo-weather
   cat /tmp/weather.lock
   ```
   Hand-edit a description in the lock file and run the proxy: it refuses to load (hash mismatch).
3. **HTTP:** three terminals:
   ```sh
   .venv/bin/demo-rugpull --http :8081
   .venv/bin/ledgerline pin --lock /tmp/r.lock --yes --http http://127.0.0.1:8081/mcp
   .venv/bin/ledgerline proxy http --upstream http://127.0.0.1:8081/mcp --listen :9000 --lock /tmp/r.lock --log /tmp/r.jsonl
   .venv/bin/demo-client --http http://127.0.0.1:9000/mcp --call get_fact_of_the_day --repeat 4
   ```
   Pin a fresh server (restart it first, or its counter has already moved).
4. **A real host through Ledgerline:**
   ```sh
   .venv/bin/ledgerline pin --lock ~/.ledgerline-demo/weather.lock --yes -- "$PWD/.venv/bin/demo-weather"
   claude mcp add weather-via-ledgerline -- "$PWD/.venv/bin/ledgerline" proxy stdio \
     --lock ~/.ledgerline-demo/weather.lock --log ~/.ledgerline-demo/weather.jsonl -- "$PWD/.venv/bin/demo-weather"
   ```
   Ask Claude Code for the weather in Pune, then read the log. Try the same with `demo-rugpull --after 1`. Remove with `claude mcp remove weather-via-ledgerline`.

## What I learned (findings from building it)

- **Transparency is testable.** Re-capturing the Phase 1 fixtures *through* the proxy gives byte-identical files, so the proxy's own verification requests are invisible to the client.
- **Per-call verification is what catches a silent rug pull.** With a host that never re-lists, the rug pull only gets blocked because the proxy asks the server before every call; with `--no-verify-each-call` it gets through (there's a test proving it).
- **Hide, don't just block.** A changed description is itself an attack, since the model reads it, so changed tools are removed from listings as well as blocked when called.
- **Hash what's on the wire.** The SDK turns tools into objects that can differ from the raw JSON, so both `ledgerline pin` and the proxy fingerprint the raw JSON.
- **Parser differentials are real.** Python's `json` keeps the *last* duplicate key, and some other parsers keep the first. A proxy that reads `{"name":"safe","name":"evil"}` differently from the server can be bypassed, so duplicates (and `NaN`, and batches) are rejected outright.
- **Headers vs body.** 2026-07-28 duplicates the method and tool name into HTTP headers for gateways. If they disagree with the body, a gateway and Ledgerline could each act on a different tool, so the proxy rejects mismatches, as the SDK's own servers do.
- **`assert` is not a safety check.** Python strips asserts under `-O`, so the proxy uses explicit checks.
- **Pinning detects change, not malice.** `demo-poisoned` pins happily if a reviewer approves it. That's why `ledgerline pin` prints every description in full.

## What surprised me

-

## Questions to carry into Phase 3

- The JSONL log can be edited by anyone. What exactly should a tamper-evident entry contain, and when must it be written relative to forwarding?
- Per-call verification doubles round trips. How much latency does it add (measure in Phase 11)?
- Known limitation (stdio): while the proxy waits for its own pre-call `tools/list`, later client messages queue behind it. If a server asked the client something (e.g. elicitation) before answering that `tools/list`, the check would time out after 30 s and the call would be **blocked** (fails closed, never open). Handling each client request in its own task would remove this; revisit with Phase 5, which also needs to hold requests.
