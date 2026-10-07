from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.sales_representatives.sales_representative_entities import SalesRepresentative


class ISalesRepresentativesRepository(ABC):
    @abstractmethod
    async def add(
        self,
        sales_representative: SalesRepresentative,
    ) -> None:
        """Добавляет торгового представителя."""

    @abstractmethod
    async def update(
        self,
        sales_representative: SalesRepresentative,
    ) -> None:
        """Сохраняет изменения торгового представителя."""

    @abstractmethod
    async def get_by_id(
        self,
        sales_representative_id: UUID,
    ) -> SalesRepresentative | None:
        """Возвращает торгового представителя по ID."""

    @abstractmethod
    async def get_all(
        self,
        include_deactivated: bool,
    ) -> list[SalesRepresentative]:
        """Возвращает всех торговых представителей."""

    @abstractmethod
    async def get_by_phone(
        self,
        phone: str,
    ) -> SalesRepresentative | None:
        """Возвращает торгового представителя по номеру телефона."""

    @abstractmethod
    async def search_by_fuzzy(
        self,
        name: str,
        phone: str,
    ) -> SalesRepresentative | None:
        """Поиск похожего торгового представителя по имени и телефону."""
