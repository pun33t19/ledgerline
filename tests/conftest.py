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


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on asyncio (the MCP SDK's default)."""
    return "asyncio"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


@pytest.fixture
def http_server(tmp_path: Path) -> Iterator[Callable[..., str]]:
    """Start a demo server over Streamable HTTP; yields a function(cmd, *args) -> URL."""
    procs: list[subprocess.Popen[bytes]] = []

    def start(cmd: str, *args: str) -> str:
        port = free_port()
        log = (tmp_path / f"{cmd}-{port}.log").open("wb")
        proc = subprocess.Popen([str(BIN / cmd), "--http", f"127.0.0.1:{port}", *args], stderr=log)  # noqa: S603
        procs.append(proc)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    return f"http://127.0.0.1:{port}/mcp"
            if proc.poll() is not None:
                break
            time.sleep(0.05)
        pytest.fail(f"{cmd} did not start; see {log.name}")

    yield start
    for proc in procs:
        proc.terminate()
        proc.wait(timeout=10)
