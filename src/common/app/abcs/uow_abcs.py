from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self

from src.common.app.abcs.event_pub_service_abcs import IEventPublisher
from src.common.domain.events import BaseDomainEvent


class InterfaceUOW(ABC):
    """
    Интерфейс Unit of Work для управления транзакциями.

    Attributes:
        _event_publisher: Требует брокер для публикации событий.
    """

    _event_publisher: IEventPublisher

    @abstractmethod
    async def __aenter__(self) -> Self:
        """Открывает транзакцию и подготавливает ресурсы."""

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Закрывает контекст. Выполняет автоматический откат при ошибке."""

    @abstractmethod
    async def commit(self, events: list[BaseDomainEvent]) -> None:
        """Фиксирует все изменения текущей транзакции в базе данных."""

    @abstractmethod
    async def rollback(self) -> None:
        """Отменяет все незафиксированные изменения."""
