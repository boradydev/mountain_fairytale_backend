from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.infra.db.postgres.database import Postgres


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управляет жизненным циклом ресурсов приложения."""
    postgres = Postgres()
    yield
    await postgres.dispose()
