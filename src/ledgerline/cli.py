"""The ``ledgerline`` command.

    ledgerline pin [--lock FILE] [--yes] -- <server command>     approve a server's tools
    ledgerline pin [--lock FILE] [--yes] --http URL
    ledgerline proxy stdio [options] -- <server command>         run in front of a local server
    ledgerline proxy http --upstream URL [--listen HOST:PORT] [options]
    ledgerline ui [--port PORT] [--no-browser]                    open the Attack Simulation Lab
    ledgerline verify --run RUN | --file ENTRIES.json             check a ledger chain
    ledgerline ledger migrate | runs | export --run RUN            manage the ledger database

Proxy options: --lock FILE, --tofu, --no-verify-each-call, and for the ledger
--ledger URL (or LEDGERLINE_DATABASE_URL), --run-id, --tenant, --user,
--digest-key FILE, --keep-args.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

import anyio
from mcp import StdioServerParameters
from mcp.client._transport import Transport
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

from ledgerline import __version__
from ledgerline.ledger.digest import DEFAULT_KEY_FILE, Digester
from ledgerline.ledger.interceptor import LedgerInterceptor
from ledgerline.ledger.store import PostgresStore
from ledgerline.ledger.verify import VerifyResult, verify_chain
from ledgerline.pin.interceptor import PinInterceptor
from ledgerline.pin.lockfile import DEFAULT_LOCKFILE, Lockfile, LockfileError
from ledgerline.pin.pinning import compare, fetch_snapshot, print_review
from ledgerline.proxy.interceptor import Chain, Interceptor

log = logging.getLogger("ledgerline")

DATABASE_ENV = "LEDGERLINE_DATABASE_URL"


def new_run_id() -> str:
    return f"{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"


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
        p.add_argument(
            "--ledger",
            metavar="URL",
            default=os.environ.get(DATABASE_ENV),
            help=f"Postgres URL to record every tool call in (default: ${DATABASE_ENV})",
        )
        p.add_argument("--run-id", default=None, help="name of this session's chain (default: time + random)")
        p.add_argument("--tenant", default="default", help="default: %(default)s")
        p.add_argument("--user", default=None, help="who the agent acts for (default: your login name)")
        p.add_argument(
            "--digest-key",
            type=Path,
            default=DEFAULT_KEY_FILE,
            help="secret key for argument fingerprints, created if missing (default: %(default)s)",
        )
        p.add_argument(
            "--keep-args",
            action="store_true",
            help="also store raw arguments (erasable, apart from the chain)",
        )

    verify = commands.add_parser("verify", help="check that a ledger chain is intact")
    source = verify.add_mutually_exclusive_group(required=True)
    source.add_argument("--run", help="a run in the ledger database")
    source.add_argument("--file", type=Path, help="a JSON array of entries (from `ledgerline ledger export`)")
    verify.add_argument("--ledger", metavar="URL", default=os.environ.get(DATABASE_ENV))

    ledger = commands.add_parser("ledger", help="manage the ledger database")
    actions = ledger.add_subparsers(dest="action", required=True)
    migrate = actions.add_parser("migrate", help="create or upgrade the tables (run as the database owner)")
    migrate.add_argument(
        "--app-password-env",
        metavar="VAR",
        help="let the ledgerline_app role log in with the password in this environment variable",
    )
    actions.add_parser("runs", help="list recorded runs")
    export = actions.add_parser("export", help="print a run's entries as JSON")
    export.add_argument("--run", required=True)
    for p in (migrate, *actions.choices.values()):
        if not any(a.dest == "ledger" for a in p._actions):
            p.add_argument("--ledger", metavar="URL", default=os.environ.get(DATABASE_ENV))
    return parser


def load_lock(path: Path, tofu: bool) -> Lockfile:
    if tofu and not path.exists():
        return Lockfile()
    return Lockfile.load(path)


def build_chain(args: argparse.Namespace, server: str) -> tuple[Interceptor, PostgresStore | None]:
    """The pin checks, wrapped by the ledger when one is configured (write-before-forward)."""
    lock = load_lock(args.lock, args.tofu)
    chain = Chain(
        [PinInterceptor(lock, lock_path=args.lock, tofu=args.tofu, verify_each_call=args.verify_each_call)]
    )
    if not args.ledger:
        log.warning("no ledger configured: tool calls are not recorded (use --ledger or $%s)", DATABASE_ENV)
        return chain, None

    def pinned_hash(name: str) -> str | None:
        pin = lock.tools.get(name)  # read at call time: --tofu adds pins as it goes
        return pin.sha256 if pin else None

    store = PostgresStore(args.ledger)
    run_id = args.run_id or new_run_id()
    ledger = LedgerInterceptor(
        chain,
        store,
        run_id=run_id,
        server=server,
        digester=Digester.from_file(args.digest_key),
        tenant=args.tenant,
        user=args.user,
        tool_hash=pinned_hash,
        keep_args=args.keep_args,
    )
    log.info("recording tool calls in the ledger as run %s", run_id)
    return ledger, store


def check_database(url: str) -> None:
    """Fail at startup, not on the first call, if the ledger database is unreachable."""
    import psycopg

    try:
        psycopg.connect(url, connect_timeout=5).close()
    except psycopg.Error as e:
        raise ValueError(f"can't reach the ledger database: {e}".strip()) from e


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

    chain, store = build_chain(args, server=" ".join(command))
    if store:
        check_database(store.url)
    proxy = StdioProxy(command, chain)

    async def run() -> int:
        try:
            return await proxy.run(stdin_lines(), write_stdout)
        finally:
            if store:
                await store.aclose()

    return anyio.run(run)


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
    chain, store = build_chain(args, server=args.upstream)
    if store:
        check_database(store.url)
    app = build_app(args.upstream, chain, guard)
    log.info("proxying http://%s:%d/mcp → %s", host, port, args.upstream)
    uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)
    return 0


def run_ui(args: argparse.Namespace) -> int:
    import secrets
    import webbrowser

    import uvicorn

    from ledgerline.api.app import create_app
    from ledgerline.api.security import LocalGuard, loopback_hosts, loopback_origins

    # A fixed token from the environment is for automated browser tests; normally it is random.
    token = os.environ.get("LEDGERLINE_UI_TOKEN") or secrets.token_urlsafe(24)
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


# What "expected" and "found" mean for each kind of break.
_LABELS = {
    "edited": ("Sealed as", "Contents hash to"),
    "broken_link": ("Previous entry", "This entry points to"),
    "bad_seq": ("Expected number", "Found number"),
    "wrong_run": ("Run", "This entry's run"),
}


def print_verify(result: VerifyResult, label: str, out: TextIO) -> None:
    if result.ok:
        print(f"✓ {label}: {result.count} entries, chain intact.", file=out)
        if result.head_hash:
            print(f"  Head hash: {result.head_hash}", file=out)
        return
    problem = result.problem
    if problem is None:  # a failed result always carries a problem
        return
    print(f"✗ {label}: {problem.message}", file=out)
    if result.verified:
        n = result.verified
        print(f"  Entries 1 to {n} are intact. Nothing from entry {n + 1} on can be trusted.", file=out)
    expected, found = _LABELS.get(problem.kind, ("Expected", "Found"))
    width = max(len(expected), len(found)) + 1
    if problem.expected:
        print(f"  {expected + ':':<{width}} {problem.expected}", file=out)
    if problem.found:
        print(f"  {found + ':':<{width}} {problem.found}", file=out)


def need_database(url: str | None) -> str:
    if not url:
        raise ValueError(f"give the ledger database with --ledger URL or ${DATABASE_ENV}")
    return url


def run_verify(args: argparse.Namespace, out: TextIO = sys.stdout) -> int:
    if args.file:
        entries: Any = json.loads(args.file.read_text(encoding="utf-8"))
        if isinstance(entries, dict) and isinstance(entries.get("entries"), list):
            entries = entries["entries"]  # a test vector (spec/vectors/*.json)
        if not isinstance(entries, list):
            raise ValueError(f"{args.file} should hold a JSON array of ledger entries")
        result = verify_chain(entries)
        print_verify(result, str(args.file), out)
        return 0 if result.ok else 1

    store = PostgresStore(need_database(args.ledger))

    async def load() -> tuple[list[Any], list[int]]:
        try:
            return await store.entries(args.run), await store.link_breaks(args.run)
        finally:
            await store.aclose()

    entries, breaks = anyio.run(load)
    if not entries:
        raise ValueError(f"no entries for run {args.run!r}")
    result = verify_chain(entries)
    print_verify(result, f"run {args.run}", out)
    # A second, independent check, done by the database itself.
    if breaks:
        print(f"  SQL check (LAG): rows out of place at seq {', '.join(map(str, breaks))}.", file=out)
    else:
        print("  SQL check (LAG): every row follows the one before it.", file=out)
    return 0 if result.ok and not breaks else 1


def run_ledger(args: argparse.Namespace, out: TextIO = sys.stdout) -> int:
    url = need_database(args.ledger)
    if args.action == "migrate":
        from ledgerline.ledger.migrate import migrate

        password = None
        if args.app_password_env:
            password = os.environ.get(args.app_password_env)
            if not password:
                raise ValueError(f"${args.app_password_env} is empty")
        applied = anyio.run(lambda: migrate(url, app_password=password))
        print(f"Applied {', '.join(applied)}." if applied else "The ledger schema is up to date.", file=out)
        return 0

    store = PostgresStore(url)
    if args.action == "runs":

        async def runs() -> list[tuple[str, int, str]]:
            try:
                return await store.runs()
            finally:
                await store.aclose()

        for run_id, count, last in anyio.run(runs):
            print(f"{run_id}  {count:>5} entries  last {last}", file=out)
        return 0

    async def export() -> list[Any]:
        try:
            return await store.entries(args.run)
        finally:
            await store.aclose()

    print(json.dumps(anyio.run(export), indent=2, ensure_ascii=False), file=out)
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
        if args.command == "verify":
            return run_verify(args)
        if args.command == "ledger":
            return run_ledger(args)
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
