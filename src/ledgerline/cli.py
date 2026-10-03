"""The ``ledgerline`` command.

    ledgerline pin [--lock FILE] [--yes] -- <server command>     approve a server's tools
    ledgerline pin [--lock FILE] [--yes] --http URL
    ledgerline proxy stdio [options] -- <server command>         run in front of a local server
    ledgerline proxy http --upstream URL [--listen HOST:PORT] [options]
    ledgerline ui [--port PORT] [--no-browser]                    open the Attack Simulation Lab

Proxy options: --lock FILE, --tofu, --no-verify-each-call, --log FILE.
"""

from __future__ import annotations

import argparse
import logging
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import TextIO

import anyio
from mcp import StdioServerParameters
from mcp.client._transport import Transport
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

from ledgerline import __version__
from ledgerline.pin.interceptor import PinInterceptor
from ledgerline.pin.lockfile import DEFAULT_LOCKFILE, Lockfile, LockfileError
from ledgerline.pin.pinning import compare, fetch_snapshot, print_review
from ledgerline.proxy.interceptor import Chain, Interceptor
from ledgerline.proxy.jsonl_log import JsonlLog

log = logging.getLogger("ledgerline")


def split_command(argv: list[str]) -> tuple[list[str], list[str]]:
    """Everything after the first ``--`` is a server command, passed through untouched."""
    if "--" in argv:
        i = argv.index("--")
        return argv[:i], argv[i + 1 :]
    return argv, []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ledgerline", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--version", action="version", version=f"ledgerline {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    ui = commands.add_parser("ui", help="open the Attack Simulation Lab in your browser")
    ui.add_argument("--port", type=int, default=8765, help="default: %(default)s")
    ui.add_argument("--no-browser", action="store_true", help="print the link but don't open a browser")
    ui.add_argument(
        "--dev", action="store_true", help="also accept the Vite dev server (http://127.0.0.1:5173)"
    )

    pin = commands.add_parser("pin", help="review a server's tools and pin their definitions")
    pin.add_argument("--lock", type=Path, default=DEFAULT_LOCKFILE, help="lock file (default: %(default)s)")
    pin.add_argument("--http", metavar="URL", help="pin a Streamable HTTP server instead of a command")
    pin.add_argument("--yes", action="store_true", help="accept without asking (for scripts)")

    proxy = commands.add_parser("proxy", help="run the proxy in front of an MCP server")
    modes = proxy.add_subparsers(dest="mode", required=True)
    stdio = modes.add_parser("stdio", help="front a local server started as a child process")
    http = modes.add_parser("http", help="front a Streamable HTTP server")
    http.add_argument(
        "--upstream", required=True, metavar="URL", help="the real server, e.g. http://127.0.0.1:8081/mcp"
    )
    http.add_argument("--listen", default="127.0.0.1:9000", metavar="HOST:PORT", help="default: %(default)s")
    http.add_argument(
        "--allow-host",
        action="append",
        default=[],
        metavar="HOST:PORT",
        help="extra Host header value to accept (needed when listening on a non-loopback address)",
    )
    for p in (stdio, http):
        p.add_argument("--lock", type=Path, default=DEFAULT_LOCKFILE, help="lock file (default: %(default)s)")
        p.add_argument(
            "--tofu", action="store_true", help="pin unknown tools on first use instead of refusing them"
        )
        p.add_argument(
            "--no-verify-each-call",
            dest="verify_each_call",
            action="store_false",
            help="don't re-fetch a tool's definition before each call (faster, misses silent rug pulls)",
        )
        p.add_argument("--log", type=Path, help="append every message and alert to this JSONL file")
    return parser


def load_lock(path: Path, tofu: bool) -> Lockfile:
    if tofu and not path.exists():
        return Lockfile()
    return Lockfile.load(path)


def build_chain(args: argparse.Namespace, files: ExitStack) -> Chain:
    lock = load_lock(args.lock, args.tofu)
    interceptors: list[Interceptor] = []
    message_log: JsonlLog | None = None
    if args.log:
        message_log = JsonlLog(files.enter_context(args.log.open("a", encoding="utf-8")))
        interceptors.append(message_log)
    interceptors.append(
        PinInterceptor(
            lock,
            lock_path=args.lock,
            tofu=args.tofu,
            verify_each_call=args.verify_each_call,
            on_alert=message_log.alert if message_log else None,
        )
    )
    return Chain(interceptors)


def run_pin(args: argparse.Namespace, command: list[str], out: TextIO = sys.stdout) -> int:
    transport: Transport
    if args.http and command:
        raise ValueError("use either --http or a server command, not both")
    if args.http:
        transport = streamable_http_client(args.http)
    elif command:
        transport = stdio_client(StdioServerParameters(command=command[0], args=command[1:]))
    else:
        raise ValueError("give a server command after -- or use --http")

    snapshot = anyio.run(fetch_snapshot, transport)
    old = Lockfile.load(args.lock) if args.lock.exists() else None
    changes = compare(old, snapshot)
    print_review(out, snapshot, changes)

    if old is not None and not changes.any:
        print(f"\n{args.lock} is up to date.", file=out)
        return 0
    if not args.yes:
        answer = input(f"\nPin these definitions in {args.lock}? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Nothing written.", file=out)
            return 1
    Lockfile(tools=snapshot.tools, server=snapshot.server).save(args.lock)
    print(f"\nWrote {len(snapshot.tools)} pin(s) to {args.lock}.", file=out)
    return 0


def run_proxy_stdio(args: argparse.Namespace, command: list[str]) -> int:
    from ledgerline.proxy.stdio import StdioProxy, stdin_lines, write_stdout

    with ExitStack() as files:
        proxy = StdioProxy(command, build_chain(args, files))
        return anyio.run(proxy.run, stdin_lines(), write_stdout)


def run_proxy_http(args: argparse.Namespace) -> int:
    import uvicorn

    from ledgerline.api.security import LocalGuard, is_loopback, loopback_hosts
    from ledgerline.demo.common import parse_host_port
    from ledgerline.proxy.http import build_app

    host, port = parse_host_port(args.listen)
    allowed = set(args.allow_host) | (loopback_hosts(port) if is_loopback(host) else set())
    if not allowed:
        log.warning("listening on %s without --allow-host: Host header checks are off", host)
    # MCP clients aren't browsers, so any Origin header means a web page is trying to reach the proxy.
    guard = LocalGuard(allowed_hosts=allowed, allowed_origins=set(), token=None, add_security_headers=False)
    with ExitStack() as files:
        app = build_app(args.upstream, build_chain(args, files), guard)
        log.info("proxying http://%s:%d/mcp → %s", host, port, args.upstream)
        uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)
    return 0


def run_ui(args: argparse.Namespace) -> int:
    import secrets
    import webbrowser

    import uvicorn

    from ledgerline.api.app import create_app
    from ledgerline.api.security import LocalGuard, loopback_hosts, loopback_origins

    token = secrets.token_urlsafe(24)
    origins = loopback_origins(args.port)
    if args.dev:
        origins |= loopback_origins(5173)
    guard = LocalGuard(allowed_hosts=loopback_hosts(args.port), allowed_origins=origins, token=token)
    url = f"http://127.0.0.1:{args.port}/?token={token}"
    print(f"\n  Ledgerline Lab: {url}\n", file=sys.stderr)
    if args.dev:
        print(f"  Dev UI:         http://127.0.0.1:5173/?token={token}\n", file=sys.stderr)
    if not args.no_browser:
        webbrowser.open(url)
    uvicorn.run(create_app(guard), host="127.0.0.1", port=args.port, log_level="warning", access_log=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    # Logs go to stderr: in stdio mode, stdout carries the protocol.
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="ledgerline: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per upstream request is noise
    own, command = split_command(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(own)

    try:
        if args.command == "pin":
            return run_pin(args, command)
        if args.command == "ui":
            return run_ui(args)
        if args.mode == "stdio":
            if not command:
                raise ValueError(
                    "give the server command after --, e.g. ledgerline proxy stdio -- demo-weather"
                )
            return run_proxy_stdio(args, command)
        if command:
            raise ValueError("proxy http takes --upstream, not a command")
        return run_proxy_http(args)
    except (LockfileError, ValueError, OSError) as e:
        log.error("%s", e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
