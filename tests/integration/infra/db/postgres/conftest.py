from collections.abc import AsyncGenerator
from typing import Any

import pytest

from src.infra.db.postgres.database import Postgres
from src.infra.db.postgres.settings import PostgresSettings


@pytest.fixture
def postgres_settings() -> PostgresSettings:
    return PostgresSettings()


@pytest.fixture
async def postgres(postgres_settings) -> AsyncGenerator[Postgres, Any]:
    postgres = Postgres(postgres_settings.DB_URL_ASYNC)
    yield postgres
    await postgres.dispose()
