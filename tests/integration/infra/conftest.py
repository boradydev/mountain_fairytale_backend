import os
import subprocess
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from sqlalchemy import text

from src.common.infra.db.postgres.database import Postgres


PROJECT_ROOT = Path(__file__).resolve().parents[3]

ALEMBIC_CONFIG = PROJECT_ROOT / "src" / "common" / "infra" / "db" / "postgres" / "alembic" / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
async def prepare_repository_database() -> AsyncGenerator[None]:
    """Prepare a clean PostgreSQL schema and apply all migrations."""
    test_database = os.environ["POSTGRES_TEST_DB"]

    previous_database = os.environ.get("POSTGRES_DB")
    os.environ["POSTGRES_DB"] = test_database

    postgres = Postgres()

    try:
        await postgres.execute(
            """
            DROP SCHEMA public CASCADE;
            CREATE SCHEMA public;
            """
        )

        subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                str(ALEMBIC_CONFIG),
                "upgrade",
                "head",
            ],
            cwd=PROJECT_ROOT,
            env=os.environ.copy(),
            check=True,
        )

        yield

    finally:
        await postgres.dispose()

        if previous_database is None:
            os.environ.pop("POSTGRES_DB", None)
        else:
            os.environ["POSTGRES_DB"] = previous_database


@pytest.fixture(autouse=True)
async def clean_repository_database(
    postgres: Postgres,
) -> None:
    """Remove all test data before every repository test."""
    async with postgres.session_factory() as session:
        result = await session.execute(
            text(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename <> 'alembic_version'
                ORDER BY tablename;
                """
            )
        )

        tables = [row.tablename for row in result]

        if not tables:
            return

        quoted_tables = ", ".join(f'"{table.replace(chr(34), chr(34) * 2)}"' for table in tables)

        await session.execute(
            text(
                f"""
                TRUNCATE TABLE {quoted_tables}
                RESTART IDENTITY
                CASCADE;
                """
            )
        )

        await session.commit()
