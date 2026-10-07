from abc import ABC, abstractmethod
from uuid import UUID

from src.feat.pay_methods.domain.pay_method_entities import PaymentMethod


class IPaymentMethodsRepository(ABC):
    @abstractmethod
    async def add(
        self,
        payment_method: PaymentMethod,
    ) -> None:
        """Добавляет способ оплаты."""

    @abstractmethod
    async def update(
        self,
        payment_method: PaymentMethod,
    ) -> None:
        """Сохраняет изменения способа оплаты."""

    @abstractmethod
    async def get_by_id(
        self,
        payment_method_id: UUID,
    ) -> PaymentMethod | None:
        """Возвращает способ оплаты по ID."""

    @abstractmethod
    async def get_all(
        self,
        include_deactivated: bool,
    ) -> list[PaymentMethod]:
        """Возвращает все способы оплаты."""

    @abstractmethod
    async def search_by_fuzzy(
        self,
        name: str,
    ) -> PaymentMethod | None:
        """Поиск способа оплаты по имени с использованием нечеткого поиска."""
