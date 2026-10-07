"""The real proxy writing to a real Postgres ledger, checked with `ledgerline verify`."""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import anyio
import pytest

from ledgerline.demo.client import Options, run
from ledgerline.ledger.store import PostgresStore
from tests.conftest import BIN, FIXTURES
from tests.ledger.test_postgres import tamper_as_superuser

pytestmark = pytest.mark.anyio

LEDGERLINE = str(BIN / "ledgerline")


def pin(lock: Path, *server: str) -> None:
    subprocess.run(
        [LEDGERLINE, "pin", "--yes", "--lock", str(lock), "--", *server], check=True, capture_output=True
    )


def proxy(tmp_path: Path, url: str, run_id: str, *server: str) -> list[str]:
    return [
        LEDGERLINE, "proxy", "stdio", "--lock", str(tmp_path / "ledgerline.lock"),
        "--ledger", url, "--run-id", run_id, "--user", "alice",
        "--digest-key", str(tmp_path / "digest.key"),
        "--", *server,
    ]  # fmt: skip


def verify(url: str, run_id: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [LEDGERLINE, "verify", "--run", run_id, "--ledger", url], capture_output=True, text=True, check=False
    )


async def entries(url: str, run_id: str) -> list[dict[str, object]]:
    store = PostgresStore(url)
    try:
        return await store.entries(run_id)
    finally:
        await store.aclose()


async def test_proxy_stays_transparent_with_the_ledger_on(tmp_path: Path, pg_app_url: str) -> None:
    server = str(BIN / "demo-weather")
    pin(tmp_path / "ledgerline.lock", server)
    wire = tmp_path / "wire.jsonl"
    opts = Options(call="get_weather", args='{"location":"Pune, IN","unit":"celsius"}', wire=wire)
    opts.command = proxy(tmp_path, pg_app_url, "transparent-1", server)

    await run(opts, io.StringIO())

    assert wire.read_text() == (FIXTURES / "weather-stdio.jsonl").read_text()
    recorded = await entries(pg_app_url, "transparent-1")
    assert [(e["kind"], e["tool"]) for e in recorded] == [
        ("request", "get_weather"),
        ("outcome", "get_weather"),
    ]
    result = verify(pg_app_url, "transparent-1")
    assert result.returncode == 0, result.stdout
    assert "2 entries, chain intact" in result.stdout


async def test_silent_rug_pull_is_recorded_and_tampering_is_caught(
    tmp_path: Path, pg_app_url: str, pg_owner_url: str
) -> None:
    server = (str(BIN / "demo-rugpull"), "--after", "3")
    pin(tmp_path / "ledgerline.lock", *server)
    command = proxy(tmp_path, pg_app_url, "rugpull-1", *server)
    await run(Options(call="get_fact_of_the_day", repeat=4, no_relist=True, command=command), io.StringIO())

    recorded = await entries(pg_app_url, "rugpull-1")
    effects = [e["decision"]["effect"] for e in recorded if e["kind"] == "request"]  # type: ignore[index]
    assert effects == ["allow", "allow", "allow", "deny"]
    blocked = recorded[-1]
    assert blocked["decision"] == {
        "effect": "deny",
        "control": "verify-before-call",
        "reason": "tool_changed",
    }
    assert blocked["actor"]["user"] == "alice"  # type: ignore[index]
    assert verify(pg_app_url, "rugpull-1").returncode == 0

    # Someone with superuser access hides the block: the chain breaks exactly there.
    seq = blocked["seq"]
    assert isinstance(seq, int)
    await tamper_as_superuser(
        pg_owner_url,
        "UPDATE ledger_entries SET entry = jsonb_set(entry, '{decision,effect}', '\"allow\"')"
        " WHERE run_id = %s AND seq = %s",
        "rugpull-1",
        seq,
    )
    result = verify(pg_app_url, "rugpull-1")
    assert result.returncode == 1
    assert f"Entry {seq} was changed after it was written" in result.stdout
    assert f"Entries 1 to {seq - 1} are intact" in result.stdout


def test_unreachable_ledger_stops_the_proxy_at_startup(tmp_path: Path) -> None:
    server = str(BIN / "demo-weather")
    pin(tmp_path / "ledgerline.lock", server)
    dead = "postgresql://nobody:x@127.0.0.1:1/none"
    result = subprocess.run(
        proxy(tmp_path, dead, "dead-1", server), capture_output=True, text=True, check=False
    )
    assert result.returncode == 2
    assert "can't reach the ledger database" in result.stderr


def test_export_then_verify_offline(tmp_path: Path, pg_app_url: str) -> None:
    store = PostgresStore(pg_app_url)

    async def write() -> None:
        try:
            await store.append({"run_id": "export-1", "kind": "request"})
            await store.append({"run_id": "export-1", "kind": "request"})
        finally:
            await store.aclose()

    anyio.run(write)
    exported = subprocess.run(
        [LEDGERLINE, "ledger", "export", "--run", "export-1", "--ledger", pg_app_url],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    path = tmp_path / "export.json"
    path.write_text(exported.stdout)
    assert len(json.loads(exported.stdout)) == 2
    result = subprocess.run(
        [LEDGERLINE, "verify", "--file", str(path)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout
