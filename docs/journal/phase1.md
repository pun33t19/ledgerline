# Phase 1 journal — MCP fundamentals

## Reading checklist

- [ ] Anthropic, *Introduction to Model Context Protocol* course
- [ ] MCP spec 2026-07-28: architecture, lifecycle, tools, transports, authorization
- [ ] Greshake et al., *Not what you've signed up for* (indirect prompt injection)
- [ ] Invariant Labs, tool-poisoning / rug-pull / shadowing post

## Try it yourself (manual tests)

1. **Run the demo:** `./demos/phase1.sh`
2. **MCP Inspector** (official debugging UI):
   ```sh
   make build-demos
   npx @modelcontextprotocol/inspector ./bin/weather
   ```
   Open each server's Tools tab. Compare what the Inspector shows for `add` (in `./bin/poisoned`) with what a chat host shows you.
3. **A real model against the poisoned server.** Use only the fake bait file:
   ```sh
   claude mcp add poisoned-demo -- "$PWD/bin/poisoned" --exfil-log ~/.ledgerline-demo/attacker-received.log
   ```
   Ask Claude Code "what is 2 + 3? use the add tool". Watch whether it reads `~/.ledgerline-demo/fake-secrets.txt`, whether the approval prompt shows the full `sidenote`, and what lands in `attacker-received.log`. Remove it afterwards with `claude mcp remove poisoned-demo`.
   Current models often refuse this, so a refusal is a valid result. Write down what happened either way.

## What I learned (findings from building it)

- **The 2026-07-28 handshake is different.** The client sends a stateless `server/discover` (SEP-2575) instead of `initialize`/`notifications/initialized`, and client info and capabilities travel in every request's `params._meta` under `io.modelcontextprotocol/*` keys. If the server doesn't support 2026-07-28, the client falls back to `initialize` with 2025-11-25.
- **In go-sdk v1.8.0 the HTTP mode decides the protocol version.** The Streamable HTTP handler only offers 2026-07-28 in `Stateless` mode. Stateful sessions negotiate 2025-11-25. The demo servers default to stateless; `--stateful` gives the legacy mode. **The Phase 2 proxy must handle both handshakes.**
- **Rug pulls can be silent.** Under 2026-07-28, `notifications/tools/list_changed` only reaches clients that subscribe (`subscriptions/listen`). Our client didn't, and the capture shows no notification. A host that never re-lists tools never learns the description changed. **Pinning can't rely on notifications.** It must hash every `tools/list` response and check the pin again before forwarding each `tools/call`.
- **The poisoned call is just valid JSON.** `{"a":2,"b":3,"sidenote":"FAKE_API_KEY=..."}` matches the schema, so nothing at the protocol level marks it as wrong. Only policy on arguments (Phase 4) or a human seeing the full arguments (Phase 5) catches it.
- **The model asks; the host does.** The demo client fills the arguments that a hijacked model would produce. The server can't tell who decided them, which is the confused deputy from Phase 0.

## What surprised me

-

## Questions to carry into Phase 2

- Should the pin cover the whole tool object (`inputSchema`, `annotations`, `title`) or only the description? (Probably everything: a changed schema can add a `sidenote` field.)
- Where does the proxy put the pin check for HTTP when the server is stateless and a "session" no longer exists?
