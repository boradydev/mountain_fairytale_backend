from abc import ABC, abstractmethod

from src.domain.common.event_record import EventRecord


class IEventRepository(ABC):
    @abstractmethod
    async def add_many(
        self,
        records: list[EventRecord],
    ) -> None:
        """Добавляет несколько событий в историю."""

    @abstractmethod
    async def get_all(
        self,
        *,
        offset: int,
        limit: int,
    ) -> list[EventRecord]:
        """Возвращает события истории с пагинацией."""
