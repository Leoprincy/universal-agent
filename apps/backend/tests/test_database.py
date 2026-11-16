import os
import time

import pytest

from app.database.connection import DatabaseConnection

TEST_DATABASE_URL = os.getenv("UGA_TEST_DATABASE_URL")


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="UGA_TEST_DATABASE_URL is not configured")
def test_database_connectivity_when_infrastructure_is_available() -> None:
    import asyncio

    async def check_database() -> str:
        database = DatabaseConnection(TEST_DATABASE_URL)
        try:
            return (await database.check()).status
        finally:
            database.close()

    assert asyncio.run(check_database()) == "connected"


def test_database_connection_failure_returns_unavailable_within_timeout() -> None:
    import asyncio

    database = DatabaseConnection("postgresql+psycopg://test:test@127.0.0.1:1/test")
    started = time.monotonic()
    try:
        result = asyncio.run(database.check())
    finally:
        database.close()

    assert result.status == "unavailable"
    assert time.monotonic() - started < 3
