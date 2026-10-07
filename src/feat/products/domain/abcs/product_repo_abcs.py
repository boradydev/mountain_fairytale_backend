from abc import ABC, abstractmethod
from uuid import UUID

from src.feat.products.domain.product_entities import Product


class IProductsRepository(ABC):
    @abstractmethod
    async def add(
        self,
        product: Product,
    ) -> None:
        """Добавляет товар."""

    @abstractmethod
    async def update(
        self,
        product: Product,
    ) -> None:
        """Сохраняет изменения товара."""

    @abstractmethod
    async def get_by_id(
        self,
        product_id: UUID,
    ) -> Product | None:
        """Возвращает товар по ID."""

    @abstractmethod
    async def get_all(
        self,
        include_deactivated: bool,
    ) -> list[Product]:
        """Возвращает все товары."""

    @abstractmethod
    async def search_by_fuzzy(
        self,
        name: str,
    ) -> Product | None:
        """Поиск товара по похожему имени."""
