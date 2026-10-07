"""A throwaway Postgres 16 (testcontainers) for the ledger's database tests.

Skipped when Docker isn't available, unless LEDGERLINE_REQUIRE_DOCKER=1 (CI sets it,
so the database tests can never be skipped silently there).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from urllib.parse import urlsplit, urlunsplit

import anyio
import pytest

from ledgerline.ledger.migrate import migrate

APP_PASSWORD = "ledgerline-test-app"


def with_user(url: str, user: str, password: str) -> str:
    parts = urlsplit(url)
    host = parts.netloc.rsplit("@", 1)[-1]
    return urlunsplit(parts._replace(netloc=f"{user}:{password}@{host}"))


@pytest.fixture(scope="session")
def pg_owner_url() -> Iterator[str]:
    try:
        from testcontainers.community.postgres import PostgresContainer

        container = PostgresContainer("postgres:16-alpine", driver=None)
        container.start()
    except Exception as e:
        if os.environ.get("LEDGERLINE_REQUIRE_DOCKER") == "1":
            raise
        pytest.skip(f"Postgres container unavailable (is Docker running?): {e}")
    try:
        url = container.get_connection_url()
        anyio.run(lambda: migrate(url, app_password=APP_PASSWORD))
        yield url
    finally:
        container.stop()


@pytest.fixture(scope="session")
def pg_app_url(pg_owner_url: str) -> str:
    """The same database as the application role (INSERT/SELECT only)."""
    return with_user(pg_owner_url, "ledgerline_app", APP_PASSWORD)
