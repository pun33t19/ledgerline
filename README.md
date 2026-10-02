# Ledgerline

Ledgerline makes every AI-agent action leave evidence. It sits between an agent and the tools and agents it calls, checks each call against least-privilege policy, pauses risky calls for human approval, and records every call, decision, approval and delegation hop in a tamper-evident log that auditors can verify offline.

It's an evidence layer designed to plug into existing MCP/A2A gateways, not another gateway. See [ADR-001](docs/adr/ADR-001-scope-evidence-layer-not-gateway.md) and [prior art](docs/prior-art.md).

> **Status:** pre-alpha, under active development. Nothing here is ready for production use.

## Development

Requires Go 1.27+ and [golangci-lint](https://golangci-lint.run/) v2.

```sh
make help            # list tasks
make ci              # vet, lint, test
./demos/phase1.sh    # tool poisoning and rug pull against the demo MCP servers
```

The demo servers in `cmd/demo-servers/` include deliberately malicious ones (`poisoned`, `rugpull`) for testing Ledgerline. They only target a fake file under `~/.ledgerline-demo/`.

## License

[Apache-2.0](LICENSE)
