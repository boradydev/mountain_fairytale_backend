from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.common.abcs.uow import InterfaceUOW
from src.domain.common.events import BaseDomainEvent


class IPostgresUOW(InterfaceUOW, ABC):
    """
    Абстрактная заготовка для Unit of Work на базе PostgreSQL.

    Реализует техническую логику транзакций, но требует конкретизации репозиториев.

    Args:
        _session_factory: Фабрика для создания асинхронных сессий базы данных.
        _session: Асинхронная сессия, требуется реализовать в __aenter__.
    """

    _session_factory: async_sessionmaker[AsyncSession]
    _session: AsyncSession

    @abstractmethod
    async def __aenter__(self) -> Self:
        """Наследник должен реализовать вход и инициализацию своих репозиториев."""

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """
        Завершает работу Unit of Work.

        Выполняет автоматический откат транзакции при возникновении исключения
        и гарантированно закрывает сессию.
        """
        try:
            if exc_type is not None:
                await self.rollback()
        finally:
            await self._session.close()

    async def commit(self, events: list[BaseDomainEvent]) -> None:
        """Фиксирует все изменения текущей транзакции в хранилище."""
        await self._event_publisher.publish_many(events=events)
        await self._session.commit()

    async def rollback(self) -> None:
        """Отменяет все незафиксированные изменения в текущей транзакции."""
        await self._session.rollback()
