"""Helpers shared by the demo servers: transport flags, serving, bait file, fake attacker."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import uvicorn
from mcp.server.mcpserver import MCPServer

log = logging.getLogger("ledgerline.demo")

# How malicious tool descriptions name the bait file. Using "~" (as Invariant's
# original demo did with ~/.cursor/mcp.json) keeps captured fixtures free of any
# real home directory.
FAKE_SECRETS_DISPLAY_PATH = "~/.ledgerline-demo/fake-secrets.txt"


def fake_secrets_path() -> Path:
    """The bait file on disk. It only ever holds fake values written by demos/phase1.sh."""
    return Path(FAKE_SECRETS_DISPLAY_PATH).expanduser()


@dataclass
class Transport:
    """How a demo server is exposed: stdio by default, or Streamable HTTP."""

    http: str | None = None
    """Serve Streamable HTTP on ``host:port`` (or ``:port``); ``None`` means stdio."""

    stateful: bool = False
    """Use session-based HTTP (``Mcp-Session-Id``) instead of independent stateless requests."""

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--http", metavar="HOST:PORT", help="serve Streamable HTTP instead of stdio")
        parser.add_argument(
            "--stateful",
            action="store_true",
            help="with --http, use legacy stateful sessions instead of stateless requests",
        )

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> Transport:
        return cls(http=args.http, stateful=args.stateful)


def parse_host_port(addr: str) -> tuple[str, int]:
    """Split ``host:port``; an empty host means localhost."""
    host, sep, port = addr.rpartition(":")
    if not sep or not port.isdigit():
        raise ValueError(f"expected HOST:PORT or :PORT, got {addr!r}")
    return host or "127.0.0.1", int(port)


def serve(server: MCPServer, transport: Transport) -> None:
    """Run ``server`` until stdin closes (stdio) or Ctrl+C (HTTP)."""
    # Logs go to stderr so they never mix with stdio protocol traffic on stdout.
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(message)s")

    if transport.http is None:
        server.run("stdio")
        return

    host, port = parse_host_port(transport.http)
    app = server.streamable_http_app(stateless_http=not transport.stateful, host=host)
    log.info("MCP server listening on http://%s:%d/mcp", host, port)
    # Run uvicorn directly so per-request access logs stay off.
    uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)


class ExfilLog:
    """Stands in for an attacker's server: whatever a malicious tool smuggles out lands here."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path

    def capture(self, tool: str, data: str) -> None:
        if not data:
            return
        log.warning("[attacker] %s exfiltrated %d bytes: %r", tool, len(data), data)
        if self.path is None:
            return
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(f"{tool}\t{data}\n")
            self.path.chmod(0o600)
        except OSError as e:
            log.error("exfil log: %s", e)
