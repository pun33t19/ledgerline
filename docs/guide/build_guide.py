"""Build docs/guide/Ledgerline-Guide.pdf: a beginner-friendly guide to how Ledgerline works.

    make guide        (or: uv run --group guide python docs/guide/build_guide.py)

Extend this file after each phase: add a phase section, update the status
table, the file reference (FILES) and the reproduce/test steps. The build
warns about any tracked file that FILES doesn't describe.
"""

from __future__ import annotations

import itertools
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from layout import (
    ACCENT,
    CLIENT,
    CLIENT_EDGE,
    CONTENT_W,
    DANGER,
    DANGER_BG,
    DATA,
    DATA_EDGE,
    FUTURE,
    FUTURE_EDGE,
    INK,
    MUTED,
    OK,
    PROXY,
    PROXY_EDGE,
    SERVER,
    SERVER_EDGE,
    SUBTITLE,
    TITLE,
    Divider,
    GuideDoc,
    Heading,
    Msg,
    Note,
    arrow,
    box,
    bullets,
    callout,
    code,
    diamond,
    elbow,
    figure,
    label,
    legend,
    make_toc,
    numbered,
    p,
    sequence,
    table,
)
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import CondPageBreak, KeepTogether, NextPageTemplate, PageBreak, Spacer

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_name("Ledgerline-Guide.pdf")
W = CONTENT_W


def hfig(title: str, level: int, fig: KeepTogether) -> list:
    """A heading plus the figure under it; starts a new page only if both won't fit on this one."""
    height = sum(f.wrap(W, 10_000)[1] for f in fig._content) + 40
    return [CondPageBreak(height), Heading(title, level), fig]


def version() -> str:
    text = (ROOT / "src/ledgerline/__init__.py").read_text()
    return text.split('__version__ = "')[1].split('"')[0]


# ===========================================================================
# Diagrams
# ===========================================================================
def d_big_picture() -> Drawing:
    d = Drawing(W, 215)
    side = 82
    box(
        d,
        0,
        80,
        side,
        64,
        "AI host",
        ["Claude Code,", "IDE, or", "demo-client"],
        CLIENT,
        CLIENT_EDGE,
        mono_lines=False,
    )
    box(
        d,
        W - side,
        80,
        side,
        64,
        "MCP tool server",
        ["weather, DB,", "email, GitHub"],
        SERVER,
        SERVER_EDGE,
        mono_lines=False,
    )
    fx, fw = side + 42, W - 2 * side - 84
    d.add(
        Rect(
            fx,
            6,
            fw,
            202,
            rx=6,
            ry=6,
            fillColor=colors.HexColor("#f7f6fd"),
            strokeColor=PROXY_EDGE,
            strokeWidth=1.2,
        )
    )
    label(d, fx + 8, 196, "LEDGERLINE (sits in the middle)", 7.5, PROXY_EDGE, bold=True)
    bx, iw = fx + 10, fw - 20
    bw = (iw - 8) / 2
    box(
        d,
        bx,
        150,
        iw,
        36,
        "Transport: stdio relay / HTTP proxy",
        ["proxy/stdio.py  proxy/http.py"],
        PROXY,
        PROXY_EDGE,
    )
    box(
        d,
        bx,
        106,
        bw,
        36,
        "Tool pinning",
        ["built in Phase 2"],
        PROXY,
        PROXY_EDGE,
        mono_lines=False,
        title_size=8,
    )
    box(
        d,
        bx + bw + 8,
        106,
        bw,
        36,
        "Message log",
        ["built in Phase 2"],
        PROXY,
        PROXY_EDGE,
        mono_lines=False,
        title_size=8,
    )
    fut = [
        ("Tamper-evident ledger", "Phase 3"),
        ("Policy + taint", "Phase 4"),
        ("Human approval", "Phase 5"),
        ("Telemetry, console…", "Phases 6–7"),
    ]
    for i, (t, ph) in enumerate(fut):
        box(
            d,
            bx + (i % 2) * (bw + 8),
            62 - (i // 2) * 44,
            bw,
            36,
            t,
            [ph],
            FUTURE,
            FUTURE_EDGE,
            dashed=True,
            mono_lines=False,
            title_size=7.6,
        )
    arrow(d, side, 124, fx, 124, "requests", size=6.2)
    arrow(d, fx, 100, side, 100, "replies", color=MUTED, dashed=True, size=6.2, label_dy=-8)
    arrow(d, fx + fw, 124, W - side, 124, "forwarded", size=6.2)
    arrow(d, W - side, 100, fx + fw, 100, "replies", color=MUTED, dashed=True, size=6.2, label_dy=-8)
    return d


def d_launch_chain() -> Drawing:
    d = Drawing(W, 300)
    steps = [
        ("1. You type a command", "ledgerline proxy stdio --lock x -- demo-weather", CLIENT, CLIENT_EDGE),
        (
            "2. Shell finds .venv/bin/ledgerline",
            "a launcher uv generated from pyproject.toml",
            DATA,
            DATA_EDGE,
        ),
        ("3. Launcher re-runs itself with Python", 'exec .venv/bin/python <launcher> "$@"', DATA, DATA_EDGE),
        (
            "4. Python fills sys.argv, calls cli.main()",
            "like Java's String[] args → main()",
            PROXY,
            PROXY_EDGE,
        ),
        ("5. split_command() + argparse", "own flags | server command after --", PROXY, PROXY_EDGE),
        (
            "6. run_proxy_stdio() builds the chain",
            "Lockfile.load → PinInterceptor → Chain",
            PROXY,
            PROXY_EDGE,
        ),
        (
            "7. anyio.run(StdioProxy.run, ...)",
            "starts the event loop; the proxy is now running",
            PROXY,
            PROXY_EDGE,
        ),
    ]
    h, gap = 34, 7
    for i, (t, sub, fill, edge) in enumerate(steps):
        y = 300 - (i + 1) * (h + gap) + gap
        box(d, 60, y, W - 120, h, t, [sub], fill, edge)
        if i:
            arrow(d, W / 2, y + h + gap, W / 2, y + h)
    return d


def d_phase1_runtime() -> Drawing:
    d = Drawing(W, 250)
    # client process
    d.add(
        Rect(
            0,
            30,
            205,
            210,
            rx=6,
            ry=6,
            fillColor=colors.HexColor("#f2f9fb"),
            strokeColor=CLIENT_EDGE,
            strokeWidth=1,
        )
    )
    label(d, 8, 228, "PROCESS 1: demo-client", 7.5, CLIENT_EDGE, bold=True)
    box(
        d,
        12,
        180,
        181,
        38,
        "client.py  main() → run()",
        ["parse_args → Options", "Client(...) handshake, list, call"],
        CLIENT,
        CLIENT_EDGE,
    )
    box(
        d,
        12,
        132,
        181,
        38,
        "wiretap.py  Wiretap (optional)",
        ["copies every message to a sink"],
        CLIENT,
        CLIENT_EDGE,
    )
    box(d, 12, 84, 181, 38, "SDK: stdio_client / HTTP", ["mcp.client.*  (library code)"], FUTURE, FUTURE_EDGE)
    box(
        d,
        12,
        40,
        181,
        34,
        "fingerprint() + report_changes()",
        ["prints a warning on change"],
        CLIENT,
        CLIENT_EDGE,
    )
    arrow(d, 102, 180, 102, 170)
    arrow(d, 102, 132, 102, 122)
    # server process
    d.add(
        Rect(
            W - 205,
            30,
            205,
            210,
            rx=6,
            ry=6,
            fillColor=colors.HexColor("#fdf8ee"),
            strokeColor=SERVER_EDGE,
            strokeWidth=1,
        )
    )
    label(d, W - 197, 228, "PROCESS 2: demo-rugpull", 7.5, SERVER_EDGE, bold=True)
    box(d, W - 193, 180, 181, 38, "rugpull.py  main()", ["argparse: --after, --http"], SERVER, SERVER_EDGE)
    box(
        d,
        W - 193,
        132,
        181,
        38,
        "common.py  serve()",
        ['stdio → server.run("stdio")', "HTTP → uvicorn"],
        SERVER,
        SERVER_EDGE,
    )
    box(d, W - 193, 84, 181, 38, "SDK: MCPServer", ["reads stdin, dispatches, replies"], FUTURE, FUTURE_EDGE)
    box(
        d,
        W - 193,
        40,
        181,
        34,
        "RugPull.get_fact()",
        ["counts calls; swaps description"],
        SERVER,
        SERVER_EDGE,
    )
    arrow(d, W - 102, 180, W - 102, 170)
    arrow(d, W - 102, 132, W - 102, 122)
    arrow(d, W - 102, 84, W - 102, 74)
    # pipes
    arrow(d, 205, 112, W - 205, 112, "requests", size=6.2)
    arrow(d, W - 205, 92, 205, 92, "replies", color=MUTED, dashed=True, size=6.2, label_dy=-8)
    label(d, W / 2, 128, "pipes: one JSON per line", 6.2, MUTED, "middle")
    label(
        d,
        W / 2,
        16,
        "stderr of the server goes straight to your terminal ([attacker] lines, logs)",
        6.8,
        MUTED,
        "middle",
    )
    return d


def d_phase2_architecture() -> Drawing:
    d = Drawing(W, 330)
    side = 74
    box(d, 0, 236, side, 60, "AI host", ["demo-client", "Claude Code"], CLIENT, CLIENT_EDGE, mono_lines=False)
    box(
        d,
        W - side,
        236,
        side,
        60,
        "Real server",
        ["demo-weather", "demo-rugpull"],
        SERVER,
        SERVER_EDGE,
        mono_lines=False,
    )
    fx, fw = side + 38, W - 2 * side - 76
    d.add(
        Rect(
            fx,
            58,
            fw,
            266,
            rx=6,
            ry=6,
            fillColor=colors.HexColor("#f7f6fd"),
            strokeColor=PROXY_EDGE,
            strokeWidth=1.2,
        )
    )
    label(d, fx + 8, 312, "LEDGERLINE PROXY (one process)", 7.5, PROXY_EDGE, bold=True)
    ix, iw = fx + 10, fw - 20
    box(d, ix, 268, iw, 38, "Transport: moves bytes", ["proxy/stdio.py | proxy/http.py + sse.py"])
    box(d, ix, 224, iw, 36, "jsonrpc.py: parse() → Message", ["rejects duplicates, NaN, batches, oversize"])
    box(d, ix, 180, iw, 36, "Upstream: the proxy's own questions", ["tools/list before each tools/call"])
    d.add(
        Rect(
            ix,
            66,
            iw,
            106,
            rx=4,
            ry=4,
            fillColor=colors.white,
            strokeColor=PROXY_EDGE,
            strokeWidth=0.8,
            strokeDashArray=[3, 2],
        )
    )
    label(d, ix + 6, 162, "Interceptor chain: Forward | Replace | Block", 7, PROXY_EDGE, bold=True)
    cw = (iw - 24) / 2
    box(
        d,
        ix + 8,
        76,
        cw,
        76,
        "JsonlLog",
        ["observe(): all msgs", "alert(): pin events", "proxy/jsonl_log.py"],
        title_size=8,
    )
    box(
        d,
        ix + 16 + cw,
        76,
        cw,
        76,
        "PinInterceptor",
        ["on_response: lists", "on_request: calls", "pin/interceptor.py"],
        title_size=8,
    )
    box(d, ix + 8, 4, cw, 34, "--log file.jsonl", ["messages + alerts"], DATA, DATA_EDGE, mono_lines=False)
    box(
        d,
        ix + 16 + cw,
        4,
        cw,
        34,
        "ledgerline.lock",
        ["approved definitions"],
        DATA,
        DATA_EDGE,
        mono_lines=False,
    )
    arrow(d, ix + 8 + cw / 2, 76, ix + 8 + cw / 2, 38, "writes", label_dx=16, size=6.2)
    arrow(d, ix + 16 + cw * 1.5, 38, ix + 16 + cw * 1.5, 76, "reads", label_dx=14, size=6.2)
    arrow(d, side, 280, fx, 280, "requests", size=6.2)
    arrow(d, fx, 254, side, 254, "replies", color=MUTED, dashed=True, size=6.2, label_dy=-8)
    arrow(d, fx + fw, 280, W - side, 280, "forwarded", size=6.2)
    arrow(d, W - side, 254, fx + fw, 254, "replies", color=MUTED, dashed=True, size=6.2, label_dy=-8)
    elbow(d, [(ix + iw, 198), (W - side / 2, 198), (W - side / 2, 236)], color=PROXY_EDGE)
    label(d, ix + iw + 6, 202, "verify", 6.2, PROXY_EDGE)
    return d


def d_modules() -> Drawing:
    d = Drawing(W, 270)
    cols = [0, (W - 110) / 3, 2 * (W - 110) / 3, W - 110]
    pos = {
        "cli.py": ((W - 110) / 2, 230),
        "proxy/stdio.py": (cols[0], 165),
        "proxy/http.py": (cols[1], 165),
        "pin/pinning.py": (cols[2], 165),
        "pin/interceptor.py": (cols[3], 165),
        "proxy/interceptor.py": (cols[0], 100),
        "proxy/jsonl_log.py": (cols[1], 100),
        "wiretap.py": (cols[2], 100),
        "pin/lockfile.py": (cols[3], 100),
        "jsonrpc.py": (cols[0], 30),
        "proxy/sse.py": (cols[1], 30),
        "pin/canonical.py": (cols[3], 30),
    }
    for name, (x, y) in pos.items():
        fill, edge = (DATA, DATA_EDGE) if name.startswith("pin") else (PROXY, PROXY_EDGE)
        if name == "cli.py":
            fill, edge = CLIENT, CLIENT_EDGE
        box(d, x, y, 110, 26, name, [], fill, edge, title_size=7.6)

    def c(n: str, top: bool) -> tuple[float, float]:
        x, y = pos[n]
        return x + 55, y + (26 if top else 0)

    for a, b in [
        ("cli.py", "proxy/stdio.py"),
        ("cli.py", "proxy/http.py"),
        ("cli.py", "pin/pinning.py"),
        ("cli.py", "pin/interceptor.py"),
        ("proxy/stdio.py", "proxy/interceptor.py"),
        ("proxy/http.py", "proxy/interceptor.py"),
        ("proxy/http.py", "proxy/sse.py"),
        ("proxy/stdio.py", "jsonrpc.py"),
        ("pin/interceptor.py", "pin/lockfile.py"),
        ("pin/interceptor.py", "proxy/interceptor.py"),
        ("pin/pinning.py", "wiretap.py"),
        ("pin/pinning.py", "pin/lockfile.py"),
        ("pin/lockfile.py", "pin/canonical.py"),
        ("proxy/jsonl_log.py", "proxy/interceptor.py"),
        ("proxy/interceptor.py", "jsonrpc.py"),
    ]:
        (ax, ay), (bx, by) = pos[a], pos[b]
        if ay == by:  # same row: connect the facing sides
            left = ax > bx
            arrow(d, ax if left else ax + 110, ay + 13, bx + 110 if left else bx, by + 13, color=MUTED)
            continue
        x1, y1 = c(a, False)
        x2, y2 = c(b, True)
        arrow(d, x1, y1, x2, y2, color=MUTED)
    label(
        d,
        0,
        4,
        'Arrow = "imports" (uses). Like Java package dependencies: cli.py is the only entry point.',
        6.8,
        MUTED,
    )
    return d


P_CLIENT = ("client", "demo-client / AI host", CLIENT, CLIENT_EDGE)
P_PROXY = ("proxy", "Ledgerline transport", PROXY, PROXY_EDGE)
P_CHAIN = ("chain", "PinInterceptor", PROXY, PROXY_EDGE)
P_SERVER = ("server", "MCP server", SERVER, SERVER_EDGE)


def d_seq_phase1() -> Drawing:
    return sequence(
        [
            ("you", "You (shell)", DATA, DATA_EDGE),
            ("client", "demo-client", CLIENT, CLIENT_EDGE),
            ("server", "demo-rugpull", SERVER, SERVER_EDGE),
        ],
        [
            Msg("you", "client", "demo-client --call get_fact_of_the_day --repeat 4 -- demo-rugpull"),
            Msg("client", "server", "starts the server as a child process (pipes)"),
            Msg("client", "server", "server/discover  (id 1)"),
            Msg("server", "client", "name, capabilities, protocol 2026-07-28", "reply"),
            Msg("client", "server", "tools/list  (id 2)"),
            Msg("server", "client", "get_fact_of_the_day: benign description", "reply"),
            Msg("client", "client", "fingerprint() → b45a34… stored as 'pinned'"),
            Divider("calls 1 and 2: normal"),
            Msg("client", "server", "tools/call get_fact_of_the_day  (call 3)"),
            Msg("server", "server", "calls == 3 → remove_tool + add malicious version"),
            Msg("server", "client", '"Bananas are berries…" (looks normal)', "reply"),
            Msg("client", "server", "tools/list"),
            Msg("server", "client", "description now contains <IMPORTANT>…", "reply"),
            Note(("client",), "fingerprint 8d1366… ≠ b45a34… → warning", "danger"),
            Msg("client", "server", "tools/call (call 4)  — nothing stops it", "blocked"),
            Msg("server", "client", '"Honey never spoils."', "reply"),
            Note(
                ("client", "server"),
                "Phase 1 lesson: nothing sits between 'model asks' and 'server does'",
                "note",
            ),
        ],
    )


def d_seq_allowed() -> Drawing:
    return sequence(
        [P_CLIENT, P_PROXY, P_CHAIN, P_SERVER],
        [
            Msg("client", "proxy", "tools/call get_weather (id 3)"),
            Msg("proxy", "proxy", "parse(line) → Message(REQUEST)"),
            Msg("proxy", "chain", "chain.on_request(msg, upstream)"),
            Msg("chain", "server", "tools/list (id ledgerline-…-1)", "proxy"),
            Msg("server", "chain", "current tool definitions", "reply"),
            Msg("chain", "chain", "sha256(current) == pinned ✓"),
            Msg("chain", "proxy", "FORWARD", "reply"),
            Msg("proxy", "server", "original bytes of the tools/call"),
            Msg("server", "proxy", "result (id 3)", "reply"),
            Msg("proxy", "chain", "chain.on_response → FORWARD"),
            Msg("proxy", "client", "original bytes of the result", "reply"),
            Note(
                ("client", "server"),
                "The client never sees the proxy's own tools/list: its reply is caught by _StdioUpstream.resolve()",
                "ok",
            ),
        ],
    )


def d_seq_blocked() -> Drawing:
    return sequence(
        [P_CLIENT, P_PROXY, P_CHAIN, P_SERVER],
        [
            Divider("calls 1–3 forwarded as in the previous diagram"),
            Msg("server", "server", "after call 3: description swapped"),
            Msg("client", "proxy", "tools/list (host re-reads the menu)"),
            Msg("proxy", "server", "forwarded"),
            Msg("server", "proxy", "list with the CHANGED tool", "reply"),
            Msg("proxy", "chain", "on_response(tools/list)"),
            Msg("chain", "chain", "8d1366… ≠ b45a34… → drop"),
            Msg("chain", "proxy", "REPLACE: list without that tool", "reply"),
            Msg("proxy", "client", "filtered list — no <IMPORTANT> text", "reply"),
            Divider("call 4 (same even if the host never re-listed)"),
            Msg("client", "proxy", "tools/call get_fact_of_the_day (call 4)"),
            Msg("proxy", "chain", "on_request"),
            Msg("chain", "server", "tools/list (verify)", "proxy"),
            Msg("server", "chain", "changed definition", "reply"),
            Msg("chain", "proxy", "BLOCK", "blocked"),
            Msg("proxy", "client", "isError: Blocked by Ledgerline", "blocked"),
            Note(("server",), "never receives call 4", "danger"),
        ],
    )


def d_flow_on_request() -> Drawing:
    d = Drawing(W, 410)
    cx = 205
    rx = W - 100
    box(d, cx - 75, 382, 150, 22, "client request arrives", [], CLIENT, CLIENT_EDGE)
    steps_y = [345, 290, 235, 180, 125, 70]
    diamond(d, cx, steps_y[0], 150, 40, ["method ==", "tools/call ?"])
    diamond(d, cx, steps_y[1], 150, 40, ["params.name is", "a string ?"])
    diamond(d, cx, steps_y[2], 150, 40, ["verify each call?", "(default: yes)"])
    box(
        d,
        cx - 75,
        steps_y[3] - 18,
        150,
        36,
        "ask the server itself",
        ['upstream.request("tools/list")', "follows nextCursor pages"],
    )
    diamond(d, cx, steps_y[4], 150, 40, ["tool still", "listed ?"])
    diamond(d, cx, steps_y[5], 150, 40, ["sha256 == pinned ?", "(or --tofu: pin it)"])
    box(d, cx - 75, 6, 150, 26, "FORWARD original bytes", [], colors.HexColor("#e6f4ea"), OK)
    arrow(d, cx, 382, cx, steps_y[0] + 20)
    for a, b in itertools.pairwise(steps_y):
        top = b + (18 if b == steps_y[3] else 20)
        bottom = a - (18 if a == steps_y[3] else 20)
        arrow(d, cx, bottom, cx, top, "yes", label_dx=9, label_dy=-2)
    arrow(d, cx, steps_y[5] - 20, cx, 32, "yes", label_dx=9, label_dy=-2)
    outcomes = [
        (steps_y[0], "FORWARD (not a tool call)", colors.HexColor("#e6f4ea"), OK),
        (steps_y[1], "BLOCK: JSON-RPC error -32602", colors.HexColor("#fbe3e1"), DANGER),
        (steps_y[3], "BLOCK: could not verify (fail closed)", colors.HexColor("#fbe3e1"), DANGER),
        (steps_y[4], "BLOCK: server no longer lists it", colors.HexColor("#fbe3e1"), DANGER),
        (steps_y[5], "BLOCK: changed / not pinned", colors.HexColor("#fbe3e1"), DANGER),
    ]
    for y, text, fill, edge in outcomes:
        box(d, rx - 80, y - 13, 180, 26, text, [], fill, edge, title_size=7.4)
        arrow(d, cx + 75, y, rx - 80, y, "error" if y == steps_y[3] else "no", color=edge)
    box(
        d,
        0,
        steps_y[2] - 58,
        112,
        36,
        "use last listing seen",
        ["weaker: misses silent", "rug pulls (tested!)"],
        colors.HexColor("#fff4e5"),
        SERVER_EDGE,
        title_size=7.6,
    )
    elbow(d, [(cx - 75, steps_y[2]), (56, steps_y[2]), (56, steps_y[2] - 22)], color=SERVER_EDGE)
    label(d, 62, steps_y[2] + 3, "no", 6.6, SERVER_EDGE)
    return d


def d_flow_list_filter() -> Drawing:
    d = Drawing(W, 250)
    box(d, 0, 205, 140, 34, "server's tools/list reply", ["PinInterceptor.on_response"], SERVER, SERVER_EDGE)
    box(d, 175, 205, 150, 34, "for each tool:", ["sha256_hex(tool)  (RFC 8785)"])
    arrow(d, 140, 222, 175, 222)
    diamond(d, 250, 160, 150, 40, ["in the lock file ?"])
    arrow(d, 250, 205, 250, 180)
    diamond(d, 250, 95, 150, 40, ["sha256 equal ?"])
    arrow(d, 250, 140, 250, 115, "yes", label_dx=9, label_dy=-2)
    box(d, 185, 22, 130, 26, "keep the tool", [], colors.HexColor("#e6f4ea"), OK)
    arrow(d, 250, 75, 250, 48, "yes", label_dx=9, label_dy=-2)
    note_bg, note_edge = colors.HexColor("#fff8dc"), colors.HexColor("#c9a227")
    box(d, W - 140, 145, 140, 30, "--tofu ? pin + keep", ["else: drop + alert"], note_bg, note_edge)
    arrow(d, 325, 160, W - 140, 160, "no")
    box(d, W - 140, 80, 140, 30, "drop + alert", ["event: tool_changed"], DANGER_BG, DANGER)
    arrow(d, 325, 95, W - 140, 95, "no", color=DANGER)
    box(
        d,
        0,
        100,
        140,
        70,
        "after the loop",
        ["nothing dropped →", "  FORWARD (same bytes)", "something dropped →", "  REPLACE (new list)"],
        note_bg,
        note_edge,
    )
    return d


def d_pin_flow() -> Drawing:
    d = Drawing(W, 150)
    xs = [0, 100, 200, 300, 400]
    items = [
        ("ledgerline pin", ["-- <server> or", "--http URL"], CLIENT, CLIENT_EDGE),
        ("fetch_snapshot()", ["Client + Wiretap", "grab RAW tools"], PROXY, PROXY_EDGE),
        ("compare()", ["NEW / CHANGED /", "REMOVED / same"], PROXY, PROXY_EDGE),
        ("print_review()", ["shows every new or", "changed definition"], PROXY, PROXY_EDGE),
        ("Lockfile.save()", ["after you answer y", "(atomic write)"], DATA, DATA_EDGE),
    ]
    for x, (t, lines, f, e) in zip(xs, items, strict=True):
        box(d, x, 80, 92, 50, t, lines, f, e, title_size=7.8)
    for x in xs[:-1]:
        arrow(d, x + 92, 105, x + 100, 105)
    box(d, 100, 10, 92, 40, "MCP server", ["answers tools/list"], SERVER, SERVER_EDGE)
    arrow(d, 146, 80, 146, 50, both=True)
    box(
        d,
        300,
        10,
        192,
        40,
        "old ledgerline.lock (if any)",
        ["Lockfile.load() recomputes every hash"],
        DATA,
        DATA_EDGE,
    )
    arrow(d, 300, 40, 246, 80, color=MUTED)
    return d


def d_http_flow() -> Drawing:
    d = Drawing(W, 175)
    row1 = [
        ("POST /mcp", ["Starlette route"], CLIENT, CLIENT_EDGE),
        ("parse(body)", ["jsonrpc.py"], PROXY, PROXY_EDGE),
        ("check headers", ["check_routing_", "headers()"], PROXY, PROXY_EDGE),
        ("chain.on_request", ["Block → reply now"], PROXY, PROXY_EDGE),
        ("httpx → upstream", ["accept-encoding:", "identity"], SERVER, SERVER_EDGE),
    ]
    bw, gap = 88, (W - 5 * 88) / 4
    for i, (t, lines, f, e) in enumerate(row1):
        x = i * (bw + gap)
        box(d, x, 115, bw, 46, t, lines, f, e, title_size=7.6)
        if i:
            arrow(d, x - gap, 138, x, 138)
    box(
        d,
        30,
        30,
        190,
        50,
        "reply is application/json",
        ["_inspect(): parse → on_response", "Replace? send new bytes"],
    )
    box(
        d,
        W - 220,
        30,
        190,
        50,
        "reply is text/event-stream (SSE)",
        ["split_events() → event_data()", "_inspect() each; with_data()"],
    )
    arrow(d, W - 44, 115, 125, 80, color=MUTED)
    arrow(d, W - 44, 115, W - 125, 80, color=MUTED)
    label(
        d,
        W / 2,
        8,
        "GET (server event stream) and DELETE (end session) are passed straight through: HttpProxy._passthrough()",
        6.8,
        MUTED,
        "middle",
    )
    label(d, 2 * (bw + gap) + bw / 2, 104, "mismatch → HTTP 400", 6.6, DANGER, "middle")
    return d


def d_test_pyramid() -> Drawing:
    d = Drawing(W, 175)
    layers = [
        ("Demos + manual (demos/phaseN.sh, Claude Code)", 180, FUTURE, FUTURE_EDGE),
        ("End-to-end: real processes over stdio + HTTP (test_*_e2e, test_client)", 290, CLIENT, CLIENT_EDGE),
        ("Property tests: Hypothesis throws random inputs (test_jsonrpc)", 380, DATA, DATA_EDGE),
        ("Unit tests: one function or rule at a time (pin, chain, sse, lockfile…)", 470, PROXY, PROXY_EDGE),
    ]
    for i, (t, w, f, e) in enumerate(layers):
        y = 140 - i * 38
        box(d, (W - w) / 2, y, w, 32, t, [], f, e, title_size=7.6)
    label(
        d,
        W / 2,
        2,
        "Fewer, slower, more realistic at the top · many, fast, focused at the bottom (same idea as JUnit + Testcontainers)",
        6.8,
        MUTED,
        "middle",
    )
    return d


def d_ci() -> Drawing:
    d = Drawing(W, 70)
    steps = [
        "checkout",
        "uv sync --locked",
        "ruff (lint)",
        "mypy --strict",
        "pytest",
        "fixtures-check",
        "pip-audit",
    ]
    bw, gap = 62, (W - 7 * 62) / 6
    for i, s in enumerate(steps):
        x = i * (bw + gap)
        box(d, x, 22, bw, 34, s, [], DATA if i else CLIENT, DATA_EDGE if i else CLIENT_EDGE, title_size=7)
        if i:
            arrow(d, x - gap, 39, x, 39)
    label(
        d,
        W / 2,
        6,
        "GitHub Actions (.github/workflows/ci.yml) runs this on every push; any red step fails the build",
        6.8,
        MUTED,
        "middle",
    )
    return d


def d_legend() -> Drawing:
    d = Drawing(W, 22)
    legend(
        d,
        0,
        6,
        [
            ("AI host / client", CLIENT, CLIENT_EDGE),
            ("Ledgerline", PROXY, PROXY_EDGE),
            ("MCP server", SERVER, SERVER_EDGE),
            ("File / data", DATA, DATA_EDGE),
            ("Not built yet / library", FUTURE, FUTURE_EDGE),
        ],
    )
    return d


# ===========================================================================
# File reference: every tracked file, the phase it arrived in, what it does.
# ===========================================================================
FILES: dict[str, tuple[str, str]] = {
    ".editorconfig": ("0", "Editor formatting rules (UTF-8, 4-space Python, tabs in Makefile)."),
    ".github/workflows/ci.yml": (
        "0",
        "GitHub Actions: lint, type-check, tests, fixtures check, dependency audit on every push.",
    ),
    ".gitignore": ("0", "Files git must never track: `.venv/`, caches, secrets, the generated guide PDF."),
    ".python-version": ("1", "Tells uv to use Python 3.14 (like a toolchain version in Maven)."),
    "CHANGELOG.md": ("0", "What changed in each version, phase by phase."),
    "LICENSE": ("0", "Apache-2.0 open-source licence."),
    "Makefile": ("0", "Short commands: `make install`, `make ci`, `make test`, `make guide`…"),
    "README.md": ("0", "Front page: what Ledgerline is and how to run it."),
    "demos/phase0.sh": ("0", "Phase 0 demo: install + all checks pass."),
    "demos/phase1.sh": ("1", "Guided tour: honest server, poisoned menu, simulated theft, rug pull."),
    "demos/phase2.sh": (
        "2",
        "Guided tour: pin, rug pull blocked, silent rug pull blocked, why verification is on.",
    ),
    "docs/adr/ADR-000-template.md": ("0", "Template for decision records."),
    "docs/adr/ADR-001-scope-evidence-layer-not-gateway.md": (
        "0",
        "Decision: an evidence layer that plugs into gateways, not a gateway.",
    ),
    "docs/adr/ADR-002-python-for-everything.md": (
        "1",
        "Decision: Python everywhere, except a Go log service in Phase 8.",
    ),
    "docs/adr/ADR-003-canonical-json-rfc8785.md": ("2", "Decision: every hash uses RFC 8785 canonical JSON."),
    "docs/adr/ADR-004-tool-pinning-enforcement.md": (
        "2",
        "Decision: how pins are enforced (hide + block, verify every call, fail closed).",
    ),
    "docs/guide/build_guide.py": ("2", "Builds this PDF: content, diagrams, file reference."),
    "docs/guide/layout.py": ("2", "Fonts, styles and the diagram toolkit used by build_guide.py."),
    "docs/journal/phase0.md": ("0", "Your Phase 0 reading checklist and notes."),
    "docs/journal/phase1.md": ("1", "Phase 1 reading, manual tests and findings."),
    "docs/journal/phase2.md": ("2", "Phase 2 reading, manual tests, findings and a known limitation."),
    "docs/prior-art.md": ("0", "Similar projects and what is left for Ledgerline to do."),
    "docs/roadmap.md": ("1", "The master plan, Phases 0–13."),
    "pyproject.toml": ("1", "Project identity card (like pom.xml): dependencies, commands, tool settings."),
    "scripts/capture-fixtures.sh": ("1", "Re-records the wire fixtures in testdata/mcp/."),
    "src/ledgerline/__init__.py": ("1", "Marks the package; holds `__version__`."),
    "src/ledgerline/cli.py": ("2", "The `ledgerline` command: pin, proxy stdio, proxy http."),
    "src/ledgerline/demo/__init__.py": ("1", "Package marker for the demo code."),
    "src/ledgerline/demo/client.py": (
        "1",
        "The practice AI app: list, call, re-list, report changes (+ --no-relist in Phase 2).",
    ),
    "src/ledgerline/demo/common.py": (
        "1",
        "Shared server helpers: serve(), Transport flags, bait path, ExfilLog.",
    ),
    "src/ledgerline/demo/servers/__init__.py": ("1", "Package marker for the demo servers."),
    "src/ledgerline/demo/servers/poisoned.py": (
        "1",
        "Tool-poisoning server: `add` with hidden instructions.",
    ),
    "src/ledgerline/demo/servers/rugpull.py": ("1", "Rug-pull server: description swaps after N calls."),
    "src/ledgerline/demo/servers/weather.py": ("1", "Honest server: `get_weather` with canned data."),
    "src/ledgerline/jsonrpc.py": (
        "2",
        "Strict JSON-RPC parsing (`Message`), error/result builders, protocol envelope helpers.",
    ),
    "src/ledgerline/pin/__init__.py": ("2", "Package marker for tool pinning."),
    "src/ledgerline/pin/canonical.py": ("2", "RFC 8785 canonical bytes and SHA-256 fingerprints."),
    "src/ledgerline/pin/interceptor.py": ("2", "PinInterceptor: filters listings, verifies calls, alerts."),
    "src/ledgerline/pin/lockfile.py": (
        "2",
        "Reads/writes ledgerline.lock; recomputes hashes on load; atomic save.",
    ),
    "src/ledgerline/pin/pinning.py": ("2", "`ledgerline pin` logic: raw snapshot, compare, review printout."),
    "src/ledgerline/proxy/__init__.py": ("2", "Package marker for the proxy."),
    "src/ledgerline/proxy/http.py": (
        "2",
        "HTTP proxy (Starlette + httpx), header checks, JSON/SSE inspection.",
    ),
    "src/ledgerline/proxy/interceptor.py": (
        "2",
        "Interceptor base class, Chain, Forward/Replace/Block, Upstream protocol.",
    ),
    "src/ledgerline/proxy/jsonl_log.py": (
        "2",
        "`--log`: plain JSONL of messages and alerts (Phase 3 replaces it).",
    ),
    "src/ledgerline/proxy/sse.py": ("2", "Splits server-sent-event streams into messages."),
    "src/ledgerline/proxy/stdio.py": ("2", "stdio relay: two loops, verification requests, shutdown."),
    "src/ledgerline/py.typed": ("1", "Marker: this package ships type hints."),
    "src/ledgerline/wiretap.py": ("1", "Records client traffic to a file or function sink."),
    "testdata/mcp/README.md": ("1", "Explains the recorded conversations (fixtures)."),
    "tests/__init__.py": ("1", "Package marker so tests can import each other."),
    "tests/conftest.py": ("1", "Shared fixtures: asyncio backend, `spawn`, `http_server`, paths."),
    "tests/demo/__init__.py": ("1", "Package marker."),
    "tests/demo/test_client.py": ("1", "End-to-end client tests over HTTP and stdio, both handshakes."),
    "tests/demo/test_poisoned.py": ("1", "Poisoned server: hidden trap, exfil log."),
    "tests/demo/test_rugpull.py": ("1", "Rug-pull server: timing, announcement, happens once."),
    "tests/demo/test_weather.py": ("1", "Weather server: answers, errors, definition."),
    "tests/pin/__init__.py": ("2", "Package marker."),
    "tests/pin/test_canonical.py": ("2", "RFC 8785 example, key order, unsafe integers."),
    "tests/pin/test_interceptor.py": ("2", "Every pin rule with a fake server."),
    "tests/pin/test_lockfile.py": ("2", "Round trip, tamper detection, bad files."),
    "tests/proxy/__init__.py": ("2", "Package marker."),
    "tests/proxy/test_chain.py": ("2", "Chain order, first block wins, replacements propagate."),
    "tests/proxy/test_http_e2e.py": ("2", "Rug pull blocked over HTTP (3 modes); header mismatch rejected."),
    "tests/proxy/test_sse.py": ("2", "SSE splitting across chunk boundaries."),
    "tests/proxy/test_stdio_e2e.py": (
        "2",
        "Byte-identical transparency, rug pull blocked, garbage, missing lock, tofu.",
    ),
    "tests/test_cli.py": ("2", "`ledgerline pin` review, changes, declining; usage errors."),
    "tests/test_jsonrpc.py": ("2", "Message classification, rejections, Hypothesis fuzzing."),
    "tests/test_version.py": ("1", "Version format."),
    "tests/test_wiretap.py": ("1", "Recorder captures both directions; ids match."),
    "uv.lock": ("1", "Exact versions of every dependency (reproducible installs)."),
}


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout  # noqa: S607
    return [f for f in out.splitlines() if not f.endswith(".jsonl")]


# ===========================================================================
# Content
# ===========================================================================
def cover(v: str) -> list:
    return [
        Spacer(1, 120),
        p("Ledgerline", TITLE),
        Spacer(1, 8),
        p("How it works, phase by phase — a guide for Java developers new to Python", SUBTITLE),
        Spacer(1, 30),
        callout(
            "This guide explains the whole app as it stands: the architecture, every runtime flow with the exact "
            "file and function involved, the Python ideas mapped to Java, and how to reproduce and test each phase. "
            "It is regenerated after every phase (`make guide`).",
            "ok",
        ),
        Spacer(1, 40),
        table(
            ["Covers", "Version", "Generated"],
            [["Phases 0, 1 and 2", f"v{v}", date.today().isoformat()]],
            [2, 1, 1],
        ),
        NextPageTemplate("page"),
        PageBreak(),
    ]


def section_reading() -> list:
    return [
        Heading("How to read this guide", 0),
        p(
            "Start with **The big picture** and **Java → Python survival kit**. Then read the phases in order: each "
            "one builds on the previous. Every flow is shown three ways: a **diagram**, a **step table** naming the "
            "file and function at each step, and the **commands** to watch it happen yourself."
        ),
        p("Colours mean the same thing in every diagram:"),
        d_legend(),
        p(
            "In sequence diagrams, time flows **top to bottom**. Solid arrows are requests, dashed arrows are "
            "replies, purple arrows are Ledgerline asking the server something on its own, and red arrows are blocked."
        ),
        p("Inline `code` is a file, function or command. File paths are relative to the repository root."),
        Spacer(1, 10),
    ]


def section_big_picture() -> list:
    return [
        Heading("1. The big picture", 0),
        p(
            "An AI model can only write text. To act (read a database, send an email) it asks a **tool server** "
            "through **MCP**, the standard protocol for AI tools. The model _asks_; the host program _does_. "
            "Ledgerline sits exactly in that gap, as a checkpoint every request must pass through."
        ),
        figure(
            d_big_picture(),
            "Figure 1 — Where Ledgerline sits. Solid boxes exist today; dashed boxes are later phases.",
        ),
        Heading("What each phase adds", 1),
        table(
            ["Phase", "Status", "Adds", "In one sentence"],
            [
                [
                    "0",
                    "✓ v0.0.0",
                    "Repo, CI, scope, prior art",
                    "A place to build, and a written answer to “why this project?”.",
                ],
                [
                    "1",
                    "✓ v0.0.2",
                    "Demo servers + client",
                    "Things to protect (honest weather) and attackers (poisoned, rug pull) to test against.",
                ],
                [
                    "2",
                    "✓ v0.0.3",
                    "Proxy + tool pinning",
                    "Ledgerline in the middle: approved tools only, rug pulls blocked.",
                ],
                [
                    "3",
                    "next",
                    "Tamper-evident ledger",
                    "Every call recorded before it runs, in a log nobody can secretly edit.",
                ],
                [
                    "4",
                    "",
                    "Policy + taint",
                    "Rules on arguments (“SELECT on tickets only”), stricter after untrusted input.",
                ],
                ["5", "", "Human approval", "Risky calls wait for a person; silence means no."],
                ["6–13", "", "Telemetry, console, Merkle log, A2A, eval, launch", "See docs/roadmap.md."],
            ],
            [0.6, 0.9, 2, 4.5],
        ),
        Heading("The vocabulary you need", 1),
        table(
            ["Term", "Meaning", "Java-world analogy"],
            [
                [
                    "MCP",
                    "Model Context Protocol: how AI apps talk to tool servers",
                    "A REST/gRPC API standard, but for AI tools",
                ],
                [
                    "JSON-RPC 2.0",
                    'The message format MCP uses: `{"id":1,"method":"tools/call","params":{…}}`',
                    "Like a tiny RPC envelope (think JAX-RPC, but JSON)",
                ],
                [
                    "tool",
                    "One action a server offers, with a name, description and input schema",
                    "A method on a remote service + its Javadoc",
                ],
                ["`tools/list`", "“What tools do you have?” — the menu", "Reflection / service discovery"],
                ["`tools/call`", "“Run this tool with these arguments”", "A remote method invocation"],
                [
                    "stdio transport",
                    "Server runs as a child process; messages flow over stdin/stdout, one JSON per line",
                    "`ProcessBuilder` with piped streams",
                ],
                [
                    "HTTP transport",
                    "Messages are HTTP POSTs to `/mcp`; replies are JSON or a stream",
                    "A servlet endpoint",
                ],
                [
                    "rug pull",
                    "A tool silently changes its description after you approved it",
                    "A dependency swapping its code after review",
                ],
                [
                    "pin",
                    "Saved fingerprint of an approved tool definition",
                    "A checksum in a lock file (Maven `.sha1`)",
                ],
            ],
            [1.1, 3, 2.4],
        ),
        PageBreak(),
    ]


def section_java() -> list:
    return [
        Heading("2. Java → Python survival kit", 0),
        p("Everything in this codebase that looks unfamiliar from Java, mapped to what you already know."),
        Heading("Language", 1),
        table(
            ["Python (as used here)", "Java equivalent", "Notes"],
            [
                [
                    "`def f(x: int) -> str:`",
                    "`String f(int x)`",
                    "Type hints are checked by **mypy** before running, not by the interpreter.",
                ],
                ["`self`", "`this`", "Written explicitly as the first parameter of every method."],
                ["`__init__(self, ...)`", "constructor", "Fields are created by assigning `self.x = ...`."],
                ["`_name`", "`private`", "A convention only; nothing enforces it."],
                [
                    "`@dataclass class Options: ...`",
                    "`record Options(...)` / Lombok `@Data`",
                    "Generates constructor, equals, repr. `frozen=True` ≈ immutable record.",
                ],
                [
                    "`class Interceptor:` with no-op methods",
                    "abstract class with default methods",
                    "Subclasses override only what they need.",
                ],
                [
                    "`class Upstream(Protocol):`",
                    "`interface Upstream`",
                    "Structural: any class with a matching `request()` method qualifies, no `implements`.",
                ],
                ["`X | None`", "`@Nullable X` / `Optional<X>`", "mypy forces you to handle `None`."],
                [
                    "`dict[str, Any]`, `list[str]`",
                    "`Map<String, Object>`, `List<String>`",
                    "JSON objects arrive as plain dicts.",
                ],
                ["`raise ValueError(...)` / `except`", "`throw` / `catch`", "All exceptions are unchecked."],
                ["`with open(f) as x:`", "try-with-resources", "Closes `x` automatically, even on errors."],
                [
                    "`async def` / `await`",
                    "`CompletableFuture` / virtual threads",
                    "`await` pauses this function and lets others run while it waits for I/O.",
                ],
                [
                    "`async with client:`",
                    "try-with-resources for async resources",
                    "Opens a connection on entry, closes it on exit.",
                ],
                [
                    "anyio task group",
                    "`StructuredTaskScope` / `ExecutorService`",
                    "Runs tasks at once; if one fails, the others are cancelled.",
                ],
                [
                    "`lambda x: ...`, closures",
                    "lambdas",
                    "Inner functions can use variables of the outer function.",
                ],
                ["`match x: case ...`", "`switch` expression", "Used in weather.py for units."],
                ['`f"{name}!"`', "`String.format` / text blocks", "Formatted string literals."],
                [
                    '`if __name__ == "__main__":`',
                    "`public static void main`",
                    "Runs only when the file is executed directly.",
                ],
                [
                    "`@pytest.mark.parametrize`",
                    "`@ParameterizedTest`",
                    "Decorators look like annotations; they wrap functions.",
                ],
            ],
            [2.3, 2.2, 3],
        ),
        Heading("Tooling", 1),
        table(
            ["Here", "Java world", "What it does"],
            [
                ["`pyproject.toml`", "`pom.xml`", "Name, dependencies, commands, tool settings."],
                [
                    "`uv` (`make install` = `uv sync`)",
                    "Maven / Gradle",
                    "Creates `.venv/`, installs exact versions from `uv.lock`.",
                ],
                ["`.venv/`", "local repo + classpath", "This project's private Python and libraries."],
                [
                    "`[project.scripts]`",
                    "`Main-Class` / exec plugin",
                    'Turns `ledgerline = "ledgerline.cli:main"` into a command.',
                ],
                [
                    "package = folder with `__init__.py`",
                    "Java package",
                    "`src/ledgerline/pin/` ≈ `com.ledgerline.pin`.",
                ],
                [
                    "module = one `.py` file",
                    "a `.java` file",
                    "But a module can hold many classes and plain functions.",
                ],
                ["`ruff`", "Checkstyle + SpotBugs + formatter", "Lint, security checks, formatting."],
                ["`mypy --strict`", "`javac` type checking", "Catches type errors before running."],
                ["`pytest`", "JUnit 5", "Test discovery, assertions with plain `assert`."],
                [
                    "pytest fixture",
                    "`@BeforeEach` / JUnit extension",
                    "Injected by parameter name (e.g. `tmp_path`, `spawn`).",
                ],
                ["Hypothesis", "jqwik", "Property-based testing with generated inputs."],
                ["`pip-audit`", "OWASP dependency-check", "Known-vulnerability scan."],
            ],
            [2.2, 1.8, 3.5],
        ),
        Heading("Side by side", 1),
        code(
            """# Python (src/ledgerline/proxy/interceptor.py, simplified)      // Java equivalent
@dataclass(frozen=True)                                           // record Block(Map<String,Object> response,
class Block:                                                      //              String reason) {}
    response: JSON
    reason: str

class Interceptor:                                                // abstract class Interceptor {
    async def on_request(self, request, upstream) -> Decision:    //   CompletableFuture<Decision> onRequest(
        return FORWARD                                            //       Message req, Upstream up) {
                                                                  //     return completedFuture(FORWARD); }
                                                                  // }""",
            "A value class and a base class with a default method",
        ),
        code(
            """async with Client(transport, cache=None) as client:     # try (var client = new Client(transport)) {
    tools = await client.list_tools()                     #     var tools = client.listTools().join();
# connection closed here, even after an exception      # }   // closed automatically""",
            "async with ≈ try-with-resources",
        ),
        callout(
            "Python reads top to bottom and runs module-level code on import. There is no compile step: `mypy` "
            "and `ruff` play the role of the compiler's checks, which is why `make ci` runs them before tests.",
            "java",
        ),
        PageBreak(),
    ]


def section_layout() -> list:
    return [
        Heading("3. The project on disk", 0),
        code(
            """ledgerline/
├── pyproject.toml, uv.lock, Makefile   build config (≈ pom.xml + mvnw)
├── src/ledgerline/                     THE PRODUCT (≈ src/main/java)
│   ├── cli.py                          the ledgerline command          Phase 2
│   ├── jsonrpc.py                      message parsing                 Phase 2
│   ├── proxy/   interceptor, stdio, http, sse, jsonl_log               Phase 2
│   ├── pin/     canonical, lockfile, interceptor, pinning              Phase 2
│   ├── wiretap.py                      traffic recorder                Phase 1
│   └── demo/    client.py, common.py, servers/*.py                     Phase 1
├── tests/                              104 tests (≈ src/test/java)
├── testdata/mcp/*.jsonl                recorded conversations
├── demos/phaseN.sh                     guided tours
├── scripts/capture-fixtures.sh         re-records the fixtures
├── docs/  adr/ journal/ guide/ roadmap.md prior-art.md
└── .github/workflows/ci.yml            CI pipeline""",
            "Repository layout",
        ),
        p("Five commands are installed into `.venv/bin/` by `make install`:"),
        table(
            ["Command", "Runs", "Purpose"],
            [
                ["`ledgerline`", "`ledgerline.cli:main`", "The product: `pin`, `proxy stdio`, `proxy http`"],
                ["`demo-weather`", "`demo/servers/weather.py:main`", "Honest MCP server"],
                ["`demo-poisoned`", "`demo/servers/poisoned.py:main`", "Tool-poisoning MCP server"],
                ["`demo-rugpull`", "`demo/servers/rugpull.py:main`", "Rug-pull MCP server"],
                ["`demo-client`", "`demo/client.py:main`", "Practice AI app"],
            ],
            [1.3, 2.4, 3],
        ),
        *hfig(
            "Who imports whom",
            1,
            figure(d_modules(), "Figure 2 — Module dependencies of the product code (demo code omitted)."),
        ),
        CondPageBreak(380),
        Heading("How any command starts", 1),
        p(
            "Every command follows the same launch chain. There is no JVM start-up: the generated launcher re-runs "
            "itself with the project's Python, which imports the module and calls its `main()`."
        ),
        figure(d_launch_chain(), "Figure 3 — From pressing Enter to a running proxy."),
        callout(
            "`anyio.run(f, a, b)` does not read your arguments; they were parsed in step 5. It only starts the async "
            "event loop and calls `f(a, b)` inside it — like submitting the first task to an executor.",
            "note",
        ),
    ]


def section_phase0() -> list:
    return [
        Heading("4. Phase 0 — Foundations", 0),
        p(
            "No runtime behaviour yet: Phase 0 created the repository, the quality gates and the reasoning behind "
            "the project."
        ),
        table(
            ["Built", "Why it matters"],
            [
                [
                    "Apache-2.0 `LICENSE`, `README.md`, `CHANGELOG.md`",
                    "Open-source from day one; every version is explained.",
                ],
                ["`Makefile` + CI workflow", "One command (`make ci`) and GitHub both run the same checks."],
                [
                    "`docs/adr/ADR-001`",
                    "Decision: an **evidence layer** that plugs into gateways, not another gateway.",
                ],
                [
                    "`docs/prior-art.md`",
                    "What already exists (Pipelock, Agent Receipts, IETF draft…) so claims stay honest.",
                ],
            ],
            [2.5, 4],
        ),
        Heading("How to explain Phase 0", 2),
        p(
            "“Before writing code I checked what exists. Signed agent logs already exist, so Ledgerline's value is a "
            "neutral, verifiable evidence layer that plugs into gateways. The repo has CI and decision records from day one.”"
        ),
    ]


def section_phase1() -> list:
    return [
        PageBreak(),
        Heading("5. Phase 1 — MCP fundamentals", 0),
        p(
            "Phase 1 built the **test bench**: one honest server, two malicious ones, and a client that plays the AI "
            "app. Nothing protects anything yet; the point is to watch attacks succeed so Phase 2 can stop them."
        ),
        *hfig(
            "Runtime architecture",
            1,
            figure(
                d_phase1_runtime(),
                "Figure 4 — Two processes connected by pipes. Each server file plugs into the same common.serve().",
            ),
        ),
        *hfig(
            "The rug pull, step by step",
            1,
            figure(
                d_seq_phase1(),
                "Figure 5 — Phase 1: the description changes after call 3; only re-listing reveals it; call 4 still runs.",
            ),
        ),
        Heading("Flow chain: which code runs", 1),
        p("Command: `demo-client --call get_fact_of_the_day --repeat 4 -- demo-rugpull --after 3`"),
        table(
            ["#", "Process", "File → function", "What happens"],
            [
                [
                    "1",
                    "client",
                    "`client.py` → `main()`",
                    "`parse_args(sys.argv[1:])` splits at `--`; `anyio.run(run, options, stdout)`.",
                ],
                [
                    "2",
                    "client",
                    "`client.py` → `make_transport()`",
                    "Command given → `stdio_client(...)` (prepared, not started).",
                ],
                [
                    "3",
                    "client",
                    "`client.py` → `run()`",
                    '`Client(transport, cache=None, mode="auto")`; `async with` starts the server and handshakes.',
                ],
                [
                    "4",
                    "server",
                    "`rugpull.py` → `main()`",
                    "argparse reads `--after 3`; `build_server()` → `RugPull(...)` registers the benign tool.",
                ],
                [
                    "5",
                    "server",
                    "`common.py` → `serve()`",
                    'No `--http` → `server.run("stdio")`: loop reading stdin.',
                ],
                ["6", "both", "SDK", "`server/discover` → name, capabilities, protocol 2026-07-28."],
                [
                    "7",
                    "client",
                    "`client.py` → `list_tools()` + `fingerprint()`",
                    "Menu fetched; SHA-256 of each tool stored as `pinned`.",
                ],
                [
                    "8",
                    "server",
                    "`rugpull.py` → `RugPull.get_fact()`",
                    "Each call: count, capture `context`, return a fact. At call 3: `remove_tool` + `_register(malicious)` + `notify_tools_changed()`.",
                ],
                [
                    "9",
                    "client",
                    "`client.py` → `report_changes()`",
                    "Re-list after each call; fingerprint differs → prints ⚠ and the new description.",
                ],
                ["10", "both", "SDK", "Leaving `async with` closes stdin → server loop ends → both exit."],
            ],
            [0.3, 0.7, 2.3, 4.2],
        ),
        Heading("The three demo servers", 1),
        table(
            ["Server", "Tool", "Behaviour", "Teaches"],
            [
                [
                    "`weather.py`",
                    "`get_weather(location, unit)`",
                    "Canned data; unknown city → `ToolError` → `isError: true`",
                    "The baseline; tool vs protocol errors",
                ],
                [
                    "`poisoned.py`",
                    "`add(a, b, sidenote)`",
                    "Description hides `<IMPORTANT>` instructions; `sidenote` goes to `ExfilLog`",
                    "A description is text the model obeys",
                ],
                [
                    "`rugpull.py`",
                    "`get_fact_of_the_day(context)`",
                    "After N calls swaps its own description",
                    "Approval at one moment isn't approval forever",
                ],
            ],
            [1.2, 1.8, 2.8, 2],
        ),
        code(
            """def get_weather(
    location: Annotated[str, Field(description="The city and state, e.g. San Francisco, CA")],
    unit: Annotated[str, Field(description="celsius or fahrenheit")] = "fahrenheit",
) -> str:
    ...
server.add_tool(get_weather, description="Get the current weather in a given location")""",
            "weather.py — the function signature IS the tool's schema (the SDK reads the type hints)",
        ),
        callout(
            "In Java you'd annotate a method and let a framework generate an OpenAPI schema from it. Same idea: "
            "`Annotated[str, Field(description=...)]` is the annotation, and the MCP SDK generates the JSON schema the model reads.",
            "java",
        ),
        Heading("What the messages look like", 1),
        code(
            """→ {"jsonrpc":"2.0","id":1,"method":"server/discover","params":{"_meta":{...}}}
← {"jsonrpc":"2.0","id":1,"result":{"supportedVersions":["2026-07-28"],...}}
→ {"jsonrpc":"2.0","id":2,"method":"tools/list","params":{"_meta":{...}}}
← {"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"get_fact_of_the_day",
       "description":"Get a random fact of the day.","inputSchema":{...}}]}}
→ {"jsonrpc":"2.0","id":3,"method":"tools/call",
       "params":{"name":"get_fact_of_the_day","arguments":{},"_meta":{...}}}
← {"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text",
       "text":"Honey never spoils."}],"isError":false}}

_meta carries the 2026-07-28 envelope: protocolVersion, clientInfo, clientCapabilities.""",
            "testdata/mcp/rugpull-stdio.jsonl (shortened). With --legacy the first step is initialize + notifications/initialized.",
        ),
        Heading("Phase 1 findings that shaped Phase 2", 1),
        *bullets(
            [
                "**Two handshakes** exist: new `server/discover` (2026-07-28) and legacy `initialize` (2025-11-25). A proxy must relay both.",
                "**Rug pulls can be silent**: the recording contains no `list_changed` notification, because the client didn't subscribe.",
                "**Clients cache tool lists** for as long as the server says, so the guard must check what the server sends, not a cached copy.",
                "**A poisoned call is valid JSON**: nothing at the protocol level marks `sidenote` as theft.",
            ]
        ),
        Heading("How to explain Phase 1", 2),
        p(
            "“I built a test bench: an honest MCP server, a tool-poisoning server and a rug-pull server, plus a client that "
            "records traffic. It shows that nothing sits between the model's request and the server's action, and that a "
            "tool can change after approval without any notification.”"
        ),
    ]


def section_phase2() -> list:
    return [
        PageBreak(),
        Heading("6. Phase 2 — The proxy and tool pinning", 0),
        p(
            "Phase 2 puts Ledgerline **in the middle**. You approve a server's tools once with `ledgerline pin`; the "
            "proxy then forwards normal traffic byte-for-byte, hides tools that changed, and blocks calls to them — "
            "checking with the server before every call so even a silent rug pull is caught."
        ),
        *hfig(
            "Architecture",
            1,
            figure(
                d_phase2_architecture(),
                "Figure 6 — Inside the proxy: transport, parser, interceptor chain, upstream checks, and two files.",
            ),
        ),
        table(
            ["Layer", "Files", "Responsibility (one job each)"],
            [
                [
                    "Entry point",
                    "`cli.py`",
                    "Parse the command, load the lock file, build the chain, start a transport.",
                ],
                [
                    "Transport",
                    "`proxy/stdio.py`, `proxy/http.py`, `proxy/sse.py`",
                    "Move bytes; parse each message; ask the chain; forward original bytes unless told otherwise.",
                ],
                [
                    "Parser",
                    "`jsonrpc.py`",
                    "Turn bytes into `Message(kind, body, raw)`; reject anything ambiguous.",
                ],
                [
                    "Chain",
                    "`proxy/interceptor.py`",
                    "Run interceptors in order; first `Block` wins; `Replace` feeds the next.",
                ],
                ["Rules", "`pin/interceptor.py`", "Filter `tools/list`; verify `tools/call`; alert."],
                [
                    "Data",
                    "`pin/lockfile.py`, `pin/canonical.py`",
                    "Approved definitions; RFC 8785 fingerprints.",
                ],
                [
                    "Logging",
                    "`proxy/jsonl_log.py`",
                    "Every message and alert as JSON lines (editable — Phase 3 fixes that).",
                ],
            ],
            [1.1, 2.6, 3.8],
        ),
        callout(
            "The interceptor chain is the Servlet `Filter` / Spring `HandlerInterceptor` pattern. Each check is a "
            "separate class; Phases 3–6 add more interceptors (ledger, policy, approvals, telemetry) without touching the transports.",
            "java",
        ),
        *hfig(
            "Flow A — approving tools: ledgerline pin",
            1,
            figure(d_pin_flow(), "Figure 7 — `ledgerline pin -- demo-rugpull`."),
        ),
        table(
            ["#", "File → function", "What happens"],
            [
                [
                    "1",
                    "`cli.py` → `main()` → `run_pin()`",
                    "Choose stdio or HTTP transport from the arguments.",
                ],
                [
                    "2",
                    "`pin/pinning.py` → `fetch_snapshot()`",
                    "Connect with the SDK `Client`, wrapped in `Wiretap` with a function sink that grabs the **raw** `tools/list` JSON (SDK objects can add/drop fields; the proxy hashes raw JSON, so pinning must too).",
                ],
                [
                    "3",
                    "`pin/lockfile.py` → `PinnedTool.of()`",
                    "`sha256_hex(definition)` via `pin/canonical.py` (RFC 8785).",
                ],
                [
                    "4",
                    "`pin/pinning.py` → `compare()`",
                    "Against the old lock (if any): NEW / CHANGED / REMOVED / unchanged.",
                ],
                [
                    "5",
                    "`pin/pinning.py` → `print_review()`",
                    "Prints every new or changed definition in full.",
                ],
                ["6", "`cli.py` → `input()`", "“Pin these definitions? [y/N]” (skipped with `--yes`)."],
                [
                    "7",
                    "`pin/lockfile.py` → `Lockfile.save()`",
                    "Write to a temp file, then rename: never a half-written lock file.",
                ],
            ],
            [0.3, 2.4, 4.8],
        ),
        Heading("Flow B — starting the stdio proxy", 1),
        table(
            ["#", "File → function", "What happens"],
            [
                [
                    "1",
                    "`cli.py` → `main()`",
                    "`split_command()`: own flags vs server command after `--`; argparse.",
                ],
                [
                    "2",
                    "`cli.py` → `build_chain()`",
                    "`Lockfile.load()` (recomputes every hash; refuses a missing lock unless `--tofu`); creates `JsonlLog` if `--log`; creates `PinInterceptor`; wraps both in `Chain`.",
                ],
                [
                    "3",
                    "`cli.py` → `run_proxy_stdio()`",
                    "`anyio.run(proxy.run, stdin_lines(), write_stdout)`.",
                ],
                [
                    "4",
                    "`proxy/stdio.py` → `StdioProxy.run()`",
                    "`anyio.open_process(server command)`; creates `_StdioUpstream`; starts two tasks in a task group.",
                ],
                [
                    "5",
                    "task 1: `client_to_server()`",
                    "Read a line from stdin → `parse()` → `observe()` → if request: `chain.on_request()` → Forward / Replace / Block.",
                ],
                [
                    "6",
                    "task 2: `server_to_client()`",
                    "Read a line from the server → `parse()` → if it answers the proxy's own question: `upstream.resolve()` (not forwarded); else `chain.on_response()` → forward.",
                ],
                [
                    "7",
                    "shutdown",
                    "Client closes stdin → close server's stdin → wait up to 5 s → terminate if needed; server exits first → cancel the reader.",
                ],
            ],
            [0.3, 2.2, 5],
        ),
        *hfig(
            "Flow C — an allowed tool call",
            1,
            figure(
                d_seq_allowed(),
                "Figure 8 — `tools/call` with per-call verification. The proxy forwards the original bytes.",
            ),
        ),
        *hfig(
            "Flow D — the rug pull, now blocked",
            1,
            figure(
                d_seq_blocked(),
                "Figure 9 — Changed tool hidden from the menu; call 4 blocked before the server sees it.",
            ),
        ),
        *hfig(
            "The decision rules",
            1,
            figure(
                d_flow_on_request(), "Figure 10 — `PinInterceptor.on_request()` for every client request."
            ),
        ),
        figure(d_flow_list_filter(), "Figure 11 — `PinInterceptor.on_response()` for `tools/list` replies."),
        callout(
            "Why check before every call? A host that never re-lists tools would otherwise keep calling the changed "
            "tool. `tests/proxy/test_stdio_e2e.py` proves it: with `--no-verify-each-call` the silent rug pull succeeds.",
            "ok",
        ),
        *hfig(
            "Flow E — the HTTP proxy",
            1,
            figure(
                d_http_flow(),
                "Figure 12 — `ledgerline proxy http --upstream URL`: one POST through `HttpProxy._post()`.",
            ),
        ),
        p(
            "Over HTTP the same `Chain` and `PinInterceptor` are used; only the transport differs. The proxy's own "
            "verification request (`_HttpUpstream.request()`) copies the client's session headers (`authorization`, "
            "`mcp-session-id`, `mcp-protocol-version`) and protocol envelope so the server treats it like the client's own request."
        ),
        Heading("Strict parsing: why messages get rejected", 1),
        table(
            ["Rejected input", "Why"],
            [
                [
                    'Duplicate keys `{"name":"a","name":"b"}`',
                    "Python keeps the last value, other parsers the first: Ledgerline and the server could check different tools (“parser differential”).",
                ],
                ["`NaN`, `Infinity`", "Not valid JSON; parsers disagree."],
                ["Batches `[{...},{...}]`", "Removed from MCP; one message = one decision."],
                ["Over 16 MiB, invalid UTF-8", "Memory safety; ambiguity."],
                [
                    "HTTP `Mcp-Method`/`Mcp-Name` ≠ body",
                    "A gateway could route on the header while Ledgerline checks the body.",
                ],
                ["Anything unparseable from the client", "Answered with an error, never forwarded."],
            ],
            [2.2, 4.8],
        ),
        Heading("Key code, explained", 1),
        code(
            """decision = await self.chain.on_request(message, upstream)
if isinstance(decision, Block):          # instanceof
    await self._reply(to_client, decision.response)
    continue                             # the server never sees this request
if isinstance(decision, Replace):
    line = encode(decision.body)         # forward a modified message
await to_server(line)                    # otherwise: the ORIGINAL bytes""",
            "proxy/stdio.py — client_to_server(): the heart of the proxy",
        ),
        code(
            """current = await self._fetch_definition(name, request, upstream)   # ask the server itself
if current is None:
    return self._block(request, name, "tool_missing", "the server no longer lists this tool")
sha = sha256_hex(current)                                            # RFC 8785 + SHA-256
if not self._accept(name, current, sha):                             # compare with the lock file
    return self._blocked_for_pin(request, name, sha)
return FORWARD""",
            "pin/interceptor.py — on_request(), the verification path",
        ),
        callout(
            "Pinning detects **change**, not **malice**: if you approve `demo-poisoned` as it is, it stays poisoned. "
            "That is why `ledgerline pin` shows every description in full. Phases 4–5 handle the rest.",
            "warn",
        ),
        Heading("What changed compared with Phase 1", 1),
        table(
            ["Area", "Phase 1", "Phase 2"],
            [
                ["Path of a message", "client → server", "client → **Ledgerline** → server"],
                [
                    "Rug pull",
                    "Detected by the demo client only, call 4 runs",
                    "Changed tool hidden; call 4 **blocked**",
                ],
                ["Host that never re-lists", "Rug pull invisible", "Still blocked (per-call verification)"],
                ["Fingerprint", "`json.dumps(sort_keys=True)`", "RFC 8785 canonical JSON"],
                ["Approval", "none", "`ledgerline pin` + `ledgerline.lock`"],
                [
                    "Logging",
                    "`--wire` recording on the client",
                    "`--log`: every message + alerts at the proxy",
                ],
                ["demo-client", "reports changed tools", "also appeared/disappeared tools; `--no-relist`"],
                ["Tests", "21", "104"],
            ],
            [1.6, 2.6, 3.2],
        ),
        Heading("How to explain Phase 2", 2),
        p(
            "“Ledgerline now runs as a transparent proxy for stdio and HTTP MCP servers. You approve tool definitions once; "
            "they're fingerprinted with RFC 8785 and saved. If a tool changes, Ledgerline hides it from the model and blocks "
            "calls to it, and because it re-checks with the server before every call, it even stops rug pulls that send no "
            "notification. Normal traffic is byte-for-byte unchanged, which the tests prove by replaying recorded sessions.”"
        ),
    ]


def section_testing() -> list:
    return [
        PageBreak(),
        *hfig(
            "7. How it is tested",
            0,
            figure(d_test_pyramid(), "Figure 13 — The test pyramid used in this project."),
        ),
        table(
            ["Test file", "Kind", "Proves"],
            [
                [
                    "`tests/test_jsonrpc.py`",
                    "unit + property",
                    "Classification; every rejection; random bytes never crash the parser.",
                ],
                [
                    "`tests/pin/test_canonical.py`",
                    "unit",
                    "Matches the RFC 8785 example; key order irrelevant; unsafe ints refused.",
                ],
                [
                    "`tests/pin/test_lockfile.py`",
                    "unit",
                    "Round trip; hand edits detected; bad files rejected clearly.",
                ],
                [
                    "`tests/pin/test_interceptor.py`",
                    "unit (fake server)",
                    "Each pin rule, fail-closed behaviour, pagination, envelope copying.",
                ],
                ["`tests/proxy/test_chain.py`", "unit", "Order, first block wins, replacements propagate."],
                ["`tests/proxy/test_sse.py`", "unit", "Event splitting across chunk boundaries."],
                [
                    "`tests/proxy/test_stdio_e2e.py`",
                    "end-to-end",
                    "**Byte-identical** replay of fixtures; rug pull blocked; garbage; missing lock; tofu.",
                ],
                [
                    "`tests/proxy/test_http_e2e.py`",
                    "end-to-end",
                    "Rug pull blocked in 3 HTTP modes; header mismatch → 400.",
                ],
                ["`tests/test_cli.py`", "integration", "`pin` review, change report, declining."],
                ["`tests/demo/*`, `test_wiretap.py`", "unit + e2e", "Phase 1 servers, client and recorder."],
            ],
            [2.4, 1.3, 3.8],
        ),
        *hfig("Continuous integration", 1, figure(d_ci(), "Figure 14 — The CI pipeline.")),
        callout(
            "pytest fixtures are injected by **parameter name**: a test that declares `tmp_path` gets a fresh temp folder, "
            "one that declares `spawn` gets a helper that starts a server on a free port and stops it afterwards "
            "(`tests/conftest.py`). Think JUnit extensions + `@TempDir`.",
            "java",
        ),
    ]


def section_reproduce() -> list:
    return [
        PageBreak(),
        Heading("8. Reproduce and test every phase", 0),
        p("Run everything from the repository folder:"),
        code(
            "cd ~/App\\ projects/ledgerline\nmake install          # creates .venv and installs the commands"
        ),
        Heading("All automated checks", 1),
        code(
            """make ci               # ruff + mypy --strict + all 104 tests   (≈ 40 s)
make fixtures-check   # re-record fixtures; fails if they changed
make vuln             # dependency vulnerability audit
make guide            # rebuild this PDF""",
        ),
        Heading("Phase 0", 1),
        code('./demos/phase0.sh     # expect: "Phase 0 OK: toolchain, lint, type checks and tests pass."'),
        Heading("Phase 1", 1),
        code(
            """./demos/phase1.sh     # press Enter between sections
# expect: weather answer · poisoned <IMPORTANT> text · "Attacker received: FAKE_API_KEY=..."
#         · rug pull: "⚠ Tool ... changed after call 3", call 4 still answered

# by hand:
.venv/bin/demo-client -- .venv/bin/demo-poisoned                       # read the hidden description
.venv/bin/demo-client --legacy --call get_weather --args '{"location":"Pune, IN"}' -- .venv/bin/demo-weather
uv run pytest tests/demo tests/test_wiretap.py -v                      # Phase 1 tests only""",
        ),
        Heading("Phase 2", 1),
        code(
            """./demos/phase2.sh     # expect: pin review · call 4 "Blocked by Ledgerline" (twice) · step 4 gets through · alerts

# by hand, stdio:
.venv/bin/ledgerline pin --lock /tmp/r.lock -- .venv/bin/demo-rugpull --after 3
.venv/bin/demo-client --call get_fact_of_the_day --repeat 4 -- \\
    .venv/bin/ledgerline proxy stdio --lock /tmp/r.lock --log /tmp/r.jsonl -- .venv/bin/demo-rugpull --after 3
cat /tmp/r.jsonl      # every message + alerts

# by hand, HTTP (3 terminals):
.venv/bin/demo-rugpull --http :8081
.venv/bin/ledgerline pin --yes --lock /tmp/h.lock --http http://127.0.0.1:8081/mcp     # then restart the server
.venv/bin/ledgerline proxy http --upstream http://127.0.0.1:8081/mcp --listen :9000 --lock /tmp/h.lock
.venv/bin/demo-client --http http://127.0.0.1:9000/mcp --call get_fact_of_the_day --repeat 4

uv run pytest tests/pin tests/proxy tests/test_jsonrpc.py tests/test_cli.py -v    # Phase 2 tests only""",
        ),
        Heading("Try it with a real AI host (optional)", 2),
        code(
            """.venv/bin/ledgerline pin --yes --lock ~/.ledgerline-demo/weather.lock -- "$PWD/.venv/bin/demo-weather"
claude mcp add weather-via-ledgerline -- "$PWD/.venv/bin/ledgerline" proxy stdio \\
    --lock ~/.ledgerline-demo/weather.lock --log ~/.ledgerline-demo/weather.jsonl -- "$PWD/.venv/bin/demo-weather"
# ask Claude Code for the weather in Pune, then:  claude mcp remove weather-via-ledgerline""",
        ),
        callout(
            "The malicious demo servers only ever target the fake file `~/.ledgerline-demo/fake-secrets.txt`.",
            "note",
        ),
    ]


def section_limits() -> list:
    return [
        Heading("9. Known limits and what comes next", 0),
        table(
            ["Limit today", "Addressed in"],
            [
                [
                    "Pinning detects change, not malice (an approved poisoned tool stays poisoned)",
                    "Phase 4 (argument rules + taint), Phase 5 (human approval)",
                ],
                [
                    "`--log` is plain JSON anyone can edit",
                    "Phase 3 (hash-chained ledger + `ledgerline verify`)",
                ],
                [
                    "Each call costs one extra `tools/list` round trip",
                    "Measured in Phase 11; `--no-verify-each-call` trades safety for speed",
                ],
                [
                    "stdio: client messages queue behind a verification; a server that asks the client something mid-check times out (fails closed)",
                    "Revisit in Phase 5",
                ],
                ["One lock file per upstream server; server names are self-reported", "By design (ADR-004)"],
            ],
            [4.5, 3],
        ),
        Heading("Glossary", 1),
        table(
            ["Term", "Meaning"],
            [
                ["fail closed", "When unsure, refuse. (Fail open = when unsure, allow.)"],
                ["fixture (testdata)", "A recorded conversation used to check behaviour doesn't change."],
                ["fixture (pytest)", "A helper injected into a test by parameter name."],
                ["interceptor", "A class that sees each message and returns Forward, Replace or Block."],
                ["lock file", "`ledgerline.lock`: approved tool definitions + fingerprints."],
                ["RFC 8785 / JCS", "A standard way to write JSON so every program produces identical bytes."],
                ["SHA-256", "A 64-hex-character fingerprint; any change gives a completely different value."],
                ["SSE", "Server-Sent Events: an HTTP reply that streams several messages."],
                ["TOFU", "Trust on first use: approve a tool automatically the first time it's seen."],
                ["transport", "How messages travel: stdio pipes or HTTP."],
                ["upstream", "The real server behind the proxy."],
            ],
            [1.6, 5.5],
        ),
    ]


def section_files() -> list:
    rows = []
    tracked = tracked_files()
    for f in tracked:
        phase, desc = FILES.get(f, ("?", "(not yet described in the guide)"))
        rows.append([f"`{f}`", phase, desc])
    rows.append(
        [
            "`testdata/mcp/*.jsonl`",
            "1",
            "Four recorded conversations (weather, weather-legacy, poisoned, rug pull).",
        ]
    )
    return [
        PageBreak(),
        Heading("Appendix — Every file in the repository", 0),
        p("Phase = when the file first appeared. Generated from `git ls-files`, so nothing is missed."),
        table(["File", "Phase", "Purpose"], rows, [3.4, 0.5, 3.6]),
    ]


def build() -> None:
    v = version()
    doc = GuideDoc(str(OUT), "Ledgerline — how it works", v)
    story = [*cover(v)]
    story += [
        p("Contents", ParagraphStyle("toc_title", parent=TITLE, fontSize=20, leading=26)),
        Spacer(1, 6),
        make_toc(),
        PageBreak(),
    ]
    for section in (
        section_reading,
        section_big_picture,
        section_java,
        section_layout,
        section_phase0,
        section_phase1,
        section_phase2,
        section_testing,
        section_reproduce,
        section_limits,
        section_files,
    ):
        story += section()
    doc.multiBuild(story)

    undocumented = [f for f in tracked_files() if f not in FILES]
    print(f"wrote {OUT.relative_to(ROOT)}")
    if undocumented:
        print("files not described in FILES (add them):", *undocumented, sep="\n  ")


if __name__ == "__main__":
    _ = (ACCENT, DANGER, INK, MUTED, numbered)  # re-exported for future sections
    build()
