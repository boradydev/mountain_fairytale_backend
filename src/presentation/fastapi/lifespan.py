from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.infra.deps.app_ctx import AppContext
from src.infra.db.postgres.database import Postgres


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управляет жизненным циклом ресурсов приложения."""
    postgres = Postgres()

    ctx = AppContext(
        postgres_session_factory=postgres.session_factory,
    )

    app.state.ctx = ctx  # type: ignore[assignment]
    yield
    await postgres.dispose()
