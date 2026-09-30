from collections.abc import AsyncGenerator
from typing import Any

import pytest

from src.infra.db.postgres.database import Postgres


@pytest.fixture
async def postgres() -> AsyncGenerator[Postgres, Any]:
    postgres = Postgres()
    yield postgres
    await postgres.dispose()
