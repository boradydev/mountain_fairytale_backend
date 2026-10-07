from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.drivers.driver_entities import Driver


class IDriversRepository(ABC):
    @abstractmethod
    async def add(self, driver: Driver) -> None:
        """Добавляет водителя."""

    @abstractmethod
    async def update(self, driver: Driver) -> None:
        """Сохраняет изменения водителя."""

    @abstractmethod
    async def get_by_id(self, driver_id: UUID) -> Driver | None:
        """Возвращает водителя по ID."""

    @abstractmethod
    async def get_all(self, include_deactivated: bool) -> list[Driver]:
        """Возвращает всех водителей."""

    @abstractmethod
    async def search_by_fuzzy(self, name: str) -> Driver | None:
        """Поиск водителя по имени с использованием нечеткого поиска."""
