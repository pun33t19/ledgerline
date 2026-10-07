"""The Postgres ledger: append-only, chained under concurrency, and tampering is detected."""

from __future__ import annotations

import secrets
from typing import Any

import anyio
import psycopg
import pytest

from ledgerline.ledger.migrate import migrate
from ledgerline.ledger.store import PostgresStore
from ledgerline.ledger.verify import verify_chain

pytestmark = pytest.mark.anyio


def fields(run_id: str, n: int = 0) -> dict[str, Any]:
    return {"run_id": run_id, "kind": "request", "tool": f"tool_{n}", "decision": {"effect": "allow"}}


async def write(url: str, run_id: str, count: int) -> list[dict[str, Any]]:
    store = PostgresStore(url)
    try:
        return [await store.append(fields(run_id, i)) for i in range(count)]
    finally:
        await store.aclose()


async def test_migrations_apply_once(pg_owner_url: str) -> None:
    assert await migrate(pg_owner_url) == []  # already applied by the fixture


async def test_app_role_appends_and_reads_a_valid_chain(pg_app_url: str) -> None:
    run = f"run-{secrets.token_hex(4)}"
    written = await write(pg_app_url, run, 3)
    store = PostgresStore(pg_app_url)
    try:
        stored = await store.entries(run)
        assert stored == written
        assert verify_chain(stored).ok
        assert await store.link_breaks(run) == []
    finally:
        await store.aclose()


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE ledger_entries SET entry = jsonb_set(entry, '{tool}', '\"x\"') WHERE run_id = %s",
        "DELETE FROM ledger_entries WHERE run_id = %s",
    ],
)
async def test_app_role_cannot_rewrite_or_delete(pg_app_url: str, statement: str) -> None:
    run = f"run-{secrets.token_hex(4)}"
    await write(pg_app_url, run, 1)
    async with await psycopg.AsyncConnection.connect(pg_app_url) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await conn.execute(statement.encode(), (run,))


async def test_even_the_owner_is_stopped_by_the_trigger(pg_owner_url: str) -> None:
    run = f"run-{secrets.token_hex(4)}"
    await write(pg_owner_url, run, 1)
    async with await psycopg.AsyncConnection.connect(pg_owner_url) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="append-only"):
            await conn.execute("UPDATE ledger_entries SET seq = seq WHERE run_id = %s", (run,))
        await conn.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="append-only"):
            await conn.execute("TRUNCATE ledger_entries CASCADE")


async def tamper_as_superuser(url: str, sql: str, *params: object) -> None:
    """What an attacker with superuser access could do: switch triggers off and rewrite history."""
    async with await psycopg.AsyncConnection.connect(url) as conn:
        await conn.execute("SET session_replication_role = replica")
        await conn.execute(sql.encode(), params)
        await conn.commit()


async def test_superuser_edit_is_caught_at_that_entry(pg_owner_url: str) -> None:
    run = f"run-{secrets.token_hex(4)}"
    await write(pg_owner_url, run, 4)
    await tamper_as_superuser(
        pg_owner_url,
        "UPDATE ledger_entries SET entry = jsonb_set(entry, '{decision,effect}', '\"deny\"')"
        " WHERE run_id = %s AND seq = 3",
        run,
    )
    store = PostgresStore(pg_owner_url)
    try:
        result = verify_chain(await store.entries(run))
    finally:
        await store.aclose()
    assert result.problem is not None
    assert (result.problem.seq, result.problem.kind) == (3, "edited")
    assert result.verified == 2


async def test_superuser_delete_is_caught_by_both_checks(pg_owner_url: str) -> None:
    run = f"run-{secrets.token_hex(4)}"
    await write(pg_owner_url, run, 4)
    await tamper_as_superuser(pg_owner_url, "DELETE FROM ledger_entries WHERE run_id = %s AND seq = 2", run)
    store = PostgresStore(pg_owner_url)
    try:
        result = verify_chain(await store.entries(run))
        breaks = await store.link_breaks(run)
    finally:
        await store.aclose()
    assert result.problem is not None
    assert result.problem.kind == "bad_seq"
    assert breaks == [3]  # the SQL LAG() check independently points at the row after the gap


async def test_fifty_concurrent_writers_produce_one_unbroken_chain(pg_app_url: str) -> None:
    run = f"run-{secrets.token_hex(4)}"

    async def writer(n: int) -> None:
        store = PostgresStore(pg_app_url)
        try:
            await store.append(fields(run, n))
        finally:
            await store.aclose()

    async with anyio.create_task_group() as tg:
        for n in range(50):
            tg.start_soon(writer, n)

    store = PostgresStore(pg_app_url)
    try:
        entries = await store.entries(run)
    finally:
        await store.aclose()
    assert [e["seq"] for e in entries] == list(range(1, 51))
    assert verify_chain(entries).ok


async def test_raw_args_can_be_erased_without_breaking_the_chain(pg_app_url: str) -> None:
    run = f"run-{secrets.token_hex(4)}"
    store = PostgresStore(pg_app_url)
    try:
        await store.append(fields(run), args={"email": "someone@example.com"})
        async with await psycopg.AsyncConnection.connect(pg_app_url) as conn:
            deleted = await conn.execute("DELETE FROM ledger_args WHERE run_id = %s", (run,))
            assert deleted.rowcount == 1
        assert verify_chain(await store.entries(run)).ok
    finally:
        await store.aclose()
