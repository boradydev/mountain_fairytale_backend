from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.common.domain.event_record import AuditRecord, EventRecord


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

    @abstractmethod
    async def get_page(
        self,
        *,
        search: str,
        before_at: datetime | None,
        before_id: UUID | None,
        limit: int,
        after_at: datetime | None = None,
        after_id: UUID | None = None,
    ) -> list[AuditRecord]:
        """Возвращает аудит перед курсором либо новые записи после него."""
