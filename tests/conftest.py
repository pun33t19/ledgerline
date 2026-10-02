"""Shared pytest fixtures."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

BIN = Path(sys.executable).parent
FIXTURES = Path(__file__).parent.parent / "testdata" / "mcp"


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on asyncio (the MCP SDK's default)."""
    return "asyncio"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


Spawn = Callable[..., str]


@pytest.fixture
def spawn(tmp_path: Path) -> Iterator[Spawn]:
    """Start a long-running command that listens on a free port; returns its MCP URL.

    ``spawn("demo-rugpull", "--http", "{addr}")``: ``{addr}`` becomes 127.0.0.1:<port>.
    Every process is stopped when the test ends.
    """
    procs: list[subprocess.Popen[bytes]] = []

    def start(cmd: str, *args: str) -> str:
        port = free_port()
        addr = f"127.0.0.1:{port}"
        argv = [str(BIN / cmd), *(a.replace("{addr}", addr) for a in args)]
        log = (tmp_path / f"{cmd}-{port}.log").open("wb")
        proc = subprocess.Popen(argv, stderr=log)
        procs.append(proc)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    return f"http://{addr}/mcp"
            if proc.poll() is not None:
                break
            time.sleep(0.05)
        pytest.fail(f"{cmd} did not start; see {log.name}")

    yield start
    for proc in procs:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture
def http_server(spawn: Spawn) -> Spawn:
    """Start a demo server over Streamable HTTP: ``http_server("demo-rugpull", "--after", "2")``."""

    def start(cmd: str, *args: str) -> str:
        return spawn(cmd, "--http", "{addr}", *args)

    return start
