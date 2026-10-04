from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.infra.db.postgres.settings import PostgresSettings


class Postgres:
    _engine: AsyncEngine
    _session_factory: async_sessionmaker[AsyncSession]

    def __init__(
        self,
        settings: PostgresSettings | None = None,
    ) -> None:
        """
        Инициализирует PostgresDB и настраивает пул соединений.

        Args:
            settings: Настройки нужны для url.
        """
        _settings = settings or PostgresSettings()
        self._engine = create_async_engine(url=_settings.DB_URL_ASYNC)
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
        )

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    async def dispose(self) -> None:
        """Закрывает все активные соединения в пуле движка."""
        await self._engine.dispose()

    async def execute(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                text(sql),
                params or {},
            )