# Ledgerline

Ledgerline makes every AI-agent action leave evidence. It sits between an agent and the tools and agents it calls, checks each call against least-privilege policy, pauses risky calls for human approval, and records every call, decision, approval and delegation hop in a tamper-evident log that auditors can verify offline.

It's an evidence layer designed to plug into existing MCP/A2A gateways, not another gateway. See [ADR-001](docs/adr/ADR-001-scope-evidence-layer-not-gateway.md), [prior art](docs/prior-art.md) and the [roadmap](docs/roadmap.md).

> **Status:** pre-alpha, under active development. Nothing here is ready for production use.

## Development

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
make install         # create .venv and install dependencies
make help            # list tasks
make ci              # lint, type-check, test
./demos/phase1.sh    # tool poisoning and rug pull against the demo MCP servers
./demos/phase2.sh    # Ledgerline pins tool definitions and blocks the rug pull
```

## Using the proxy

```sh
ledgerline pin -- <server command>                     # review and approve the server's tools
ledgerline proxy stdio -- <server command>             # then run your MCP host against this
ledgerline proxy http --upstream http://host:port/mcp  # or front an HTTP server on :9000/mcp
```

Ledgerline forwards normal traffic unchanged, hides tools whose definition changed since they were pinned, and blocks calls to them. See [ADR-004](docs/adr/ADR-004-tool-pinning-enforcement.md).

The demo servers in `src/ledgerline/demo/servers/` include deliberately malicious ones (`demo-poisoned`, `demo-rugpull`) for testing Ledgerline. They only target a fake file under `~/.ledgerline-demo/`.

## License

[Apache-2.0](LICENSE)
