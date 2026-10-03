# Phase 3 journal — Attack Simulation Lab

## Reading checklist

- [ ] React docs, "Learn" section (components, props, state, effects)
- [ ] TypeScript handbook: basics, narrowing, unions
- [ ] Vite guide; TanStack Query overview; Radix primitives (Dialog, Tabs, Switch)
- [ ] FastAPI: path operations, WebSockets, lifespan
- [ ] OWASP MCP Top 10 and OWASP Agentic Top 10 (the categories the Lab tags)
- [ ] MCP spec security guidance on `Origin` validation and DNS rebinding
- [ ] `docs/research/ui-research.md` (why the Lab looks the way it does)

## Try it yourself

```sh
make install && make web-install     # once
./demos/phase3.sh                    # builds the UI and opens the Lab
```

For UI development with hot reload (two terminals):

```sh
uv run ledgerline ui --dev --no-browser --port 8765   # prints a token
cd web && npm run dev                                  # open http://127.0.0.1:5173/?token=<that token>
```

Tests: `make test` (Python, including every scenario), `make web-ci` (UI), `make e2e` (browser tests; run `cd web && npx playwright install chromium` once).

## What I learned (findings from building it)

- **The official MCP server accepted a message with duplicate keys** and used the *last* copy. A checker that keeps the first copy would approve a harmless-looking call while the server receives the secret. Ledgerline's strict parsing rejects it (scenario `parser-differential`).
- **Server-side malice needs no model at all.** With `--steal`, the rug-pull server reads the secret itself after the switch, so a host that never re-lists still loses data. Only "check before every call" stops it, because it blocks the call before the server runs.
- **Measured coverage is clearer than claims.** Re-running each attack with one control off shows exactly which control is load-bearing (`/coverage`).
- **Local web servers are attack surface.** The Lab and `ledgerline proxy http` now reject foreign `Host` and `Origin` headers (DNS rebinding) and the Lab requires the printed token. The WebSocket test caught that the guard covers WebSockets too.
- **A real concurrency bug:** the event WebSocket marked events as sent while new ones arrived mid-send, dropping 16 of 65. Counting each event as it's sent fixed it; the API test now compares the streamed count with the stored run.
- **Tooling surprise:** TypeScript 7 (the native rewrite) dropped the JS API that `openapi-typescript` needs; the UI pins TypeScript 5.9.
- **Honest limit, on screen:** tool poisoning present from day one is *not* stopped; the Lab says so and names Phases 5–6.

## Screenshots

Take your own with `./demos/phase3.sh` (light and dark themes, desktop and phone).

## What surprised me

-

## Questions to carry into Phase 4

- What exactly should each ledger entry record so the Lab's tamper demo (UI-16) can show a broken link?
- Should Lab runs write to the same Postgres ledger as real traffic, or to a separate, disposable one?
