"""A tiny migration runner: applies ``migrations/NNNN_*.sql`` in order, each once.

Run it as the database owner (it creates the ``ledgerline_app`` role and the
append-only trigger). The proxy then connects as ``ledgerline_app``.
"""

from __future__ import annotations

from importlib import resources

MIGRATIONS = resources.files("ledgerline.ledger") / "migrations"


def migration_files() -> list[tuple[str, str]]:
    """(version, sql) pairs, in order."""
    files = sorted(
        (f for f in MIGRATIONS.iterdir() if f.name.endswith(".sql")),
        key=lambda f: f.name,
    )
    return [(f.name.removesuffix(".sql"), f.read_text(encoding="utf-8")) for f in files]


async def migrate(url: str, *, app_password: str | None = None) -> list[str]:
    """Apply pending migrations; return the versions applied.

    With ``app_password``, also lets ``ledgerline_app`` log in with that password.
    """
    import psycopg
    from psycopg import sql

    applied: list[str] = []
    async with await psycopg.AsyncConnection.connect(url) as conn:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS ledger_schema_migrations"
            " (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        # Two migrators at once would race; this lock makes the second one wait, then find nothing to do.
        await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('ledgerline-migrate', 0))")
        cur = await conn.execute("SELECT version FROM ledger_schema_migrations")
        done = {row[0] for row in await cur.fetchall()}
        for version, script in migration_files():
            if version in done:
                continue
            await conn.execute(script.encode())  # no parameters: may contain several statements
            await conn.execute("INSERT INTO ledger_schema_migrations (version) VALUES (%s)", (version,))
            applied.append(version)
        if app_password is not None:
            await conn.execute(
                sql.SQL("ALTER ROLE ledgerline_app LOGIN PASSWORD {}").format(sql.Literal(app_password))
            )
        await conn.commit()
    return applied
