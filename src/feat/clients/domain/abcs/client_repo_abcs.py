from abc import ABC, abstractmethod
from uuid import UUID

from src.feat.clients.domain.client_entities import Client


class IClientsRepository(ABC):
    @abstractmethod
    async def add(self, client: Client) -> None:
        """Добавляет клиента."""

    @abstractmethod
    async def update(self, client: Client) -> None:
        """Сохраняет изменения клиента."""

    @abstractmethod
    async def get_by_id(self, client_id: UUID) -> Client | None:
        """Возвращает клиента по ID."""

    @abstractmethod
    async def get_all(
        self,
        *,
        include_deactivated: bool,
        offset: int,
        limit: int,
    ) -> tuple[list[Client], int]:
        """Возвращает страницу клиентов и общее количество подходящих записей."""

    @abstractmethod
    async def search_duplicate(
        self,
        *,
        name: str,
        phone: str,
        address: str,
    ) -> Client | None:
        """Ищет лучший подходящий дубликат по трём значениям."""
