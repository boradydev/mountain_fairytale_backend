from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.infra.db.postgres.settings import PostgresSettings


class Postgres:
    """
    Управляет жизненным циклом подключений к базе данных PostgreSQL.

    Этот класс инкапсулирует создание асинхронного движка (Engine) и фабрики
    сессий, обеспечивая централизованное управление ресурсами БД.

    Attributes:
        _engine: Экземпляр асинхронного движка SQLAlchemy.
        _session_factory : Фабрика для генерации
            новых асинхронных сессий.
    """

    _engine: AsyncEngine
    _session_factory: async_sessionmaker[AsyncSession]

    def __init__(
        self,
        settings: PostgresSettings | None = None,
    ) -> None:
        """
        Инициализирует PostgresDB и настраивает пул соединений.

        Args:
            settings: Настройки нужны дял url.
        """
        _settings = settings or PostgresSettings()
        _engine = create_async_engine(url=_settings.DB_URL_ASYNC)
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
