"""Where entries are kept.

- :class:`PostgresStore`: the real ledger. Appends are serialised per run with a
  transaction-scoped advisory lock, so concurrent writers can't fork the chain
  or reuse a ``seq``. The table is append-only (``migrations/0001_ledger.sql``).
- :class:`MemoryStore`: for Lab runs and tests: same chaining, no database.

Both seal entries the same way (``hashing.seal``) and return the sealed entry.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Protocol

import anyio

from ledgerline.jsonrpc import JSON
from ledgerline.ledger.hashing import GENESIS, seal


class LedgerStore(Protocol):
    async def append(self, fields: JSON, *, args: Any = None) -> JSON:
        """Chain ``fields`` (which include ``run_id``) after the run's last entry and store it.

        ``args``, if given, are kept in a separate, erasable table (ADR-008).
        """
        ...

    async def entries(self, run_id: str) -> list[JSON]: ...

    async def aclose(self) -> None: ...


class MemoryStore:
    def __init__(self) -> None:
        self.chains: dict[str, list[JSON]] = defaultdict(list)
        self.args: dict[tuple[str, int], Any] = {}
        self._lock = anyio.Lock()

    async def append(self, fields: JSON, *, args: Any = None) -> JSON:
        async with self._lock:
            chain = self.chains[str(fields["run_id"])]
            prev = chain[-1]["entry_hash"] if chain else GENESIS
            entry = seal(fields, seq=len(chain) + 1, prev_hash=prev)
            chain.append(entry)
            if args is not None:
                self.args[(str(fields["run_id"]), entry["seq"])] = args
            return entry

    async def entries(self, run_id: str) -> list[JSON]:
        return [dict(e) for e in self.chains.get(run_id, [])]

    async def aclose(self) -> None:
        return None


class PostgresStore:
    """One connection, used by one writer at a time; several stores can share a database."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._conn: Any = None
        self._lock = anyio.Lock()

    async def connect(self) -> None:
        import psycopg

        if self._conn is None or self._conn.closed:
            self._conn = await psycopg.AsyncConnection.connect(self.url)

    async def append(self, fields: JSON, *, args: Any = None) -> JSON:
        from psycopg.types.json import Jsonb

        run_id = str(fields["run_id"])
        async with self._lock:
            await self.connect()
            conn = self._conn
            async with conn.transaction():
                # Serialise writers of this run until commit: the "read last, write next" below can't race.
                await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (run_id,))
                cur = await conn.execute(
                    "SELECT seq, entry_hash FROM ledger_entries WHERE run_id = %s ORDER BY seq DESC LIMIT 1",
                    (run_id,),
                )
                last = await cur.fetchone()
                entry = seal(fields, seq=last[0] + 1 if last else 1, prev_hash=last[1] if last else GENESIS)
                await conn.execute(
                    "INSERT INTO ledger_entries (run_id, seq, entry_hash, prev_hash, entry)"
                    " VALUES (%s, %s, %s, %s, %s)",
                    (run_id, entry["seq"], entry["entry_hash"], entry["prev_hash"], Jsonb(entry)),
                )
                if args is not None:
                    await conn.execute(
                        "INSERT INTO ledger_args (run_id, seq, args) VALUES (%s, %s, %s)",
                        (run_id, entry["seq"], Jsonb(args)),
                    )
            return entry

    async def entries(self, run_id: str) -> list[JSON]:
        async with self._lock:
            await self.connect()
            cur = await self._conn.execute(
                "SELECT entry FROM ledger_entries WHERE run_id = %s ORDER BY seq", (run_id,)
            )
            rows = await cur.fetchall()
            await self._conn.commit()
            return [row[0] for row in rows]

    async def runs(self) -> list[tuple[str, int, str]]:
        """(run_id, entries, last written) for every run, newest first."""
        async with self._lock:
            await self.connect()
            cur = await self._conn.execute(
                "SELECT run_id, count(*), max(recorded_at)::text FROM ledger_entries"
                " GROUP BY run_id ORDER BY max(recorded_at) DESC"
            )
            rows = await cur.fetchall()
            await self._conn.commit()
            return [(str(r[0]), int(r[1]), str(r[2])) for r in rows]

    async def link_breaks(self, run_id: str) -> list[int]:
        """A second, independent check in SQL: rows whose stored prev_hash isn't the previous row's hash.

        It compares the indexed columns with ``LAG()``, so it catches removed or reordered rows;
        edited contents are caught by recomputing hashes (``verify_chain``).
        """
        async with self._lock:
            await self.connect()
            cur = await self._conn.execute(
                """
                SELECT seq FROM (
                    SELECT seq, prev_hash,
                           lag(entry_hash) OVER (ORDER BY seq) AS expected,
                           lag(seq) OVER (ORDER BY seq) AS prev_seq
                    FROM ledger_entries WHERE run_id = %s
                ) t
                WHERE prev_hash <> coalesce(expected, %s)
                   OR seq <> coalesce(prev_seq + 1, 1)
                ORDER BY seq
                """,
                (run_id, GENESIS),
            )
            rows = await cur.fetchall()
            await self._conn.commit()
            return [int(r[0]) for r in rows]

    async def aclose(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
