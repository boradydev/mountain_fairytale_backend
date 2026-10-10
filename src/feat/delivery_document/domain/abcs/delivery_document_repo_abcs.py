from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from src.feat.delivery_document.domain.delivery_document_entities import (
    DeliveryDocument,
    EditLock,
)


class IDeliveryDocumentsRepository(ABC):
    @abstractmethod
    async def add(self, document: DeliveryDocument) -> None:
        """Добавляет новый документ и сохраняет его состояние."""

    @abstractmethod
    async def update(self, document: DeliveryDocument) -> None:
        """Сохраняет изменения документа и его вложенных данных."""

    @abstractmethod
    async def get_by_id(
        self,
        delivery_document_id: UUID,
        *,
        document_type: str,
    ) -> DeliveryDocument | None:
        """Возвращает документ указанного типа по UUID."""

    @abstractmethod
    async def get_all(
        self,
        *,
        document_type: str,
        include_cancelled: bool,
        offset: int,
        limit: int,
    ) -> tuple[list[DeliveryDocument], int]:
        """Возвращает страницу документов и количество совпадений."""

    @abstractmethod
    async def get_edit_lock(
        self,
        delivery_document_id: UUID,
    ) -> EditLock | None:
        """Возвращает текущую блокировку редактирования документа."""

    @abstractmethod
    async def acquire_edit_lock(
        self,
        *,
        delivery_document_id: UUID,
        employee_id: UUID,
    ) -> str:
        """Захватывает блокировку и возвращает имя владельца."""

    @abstractmethod
    async def renew_edit_lock(
        self,
        *,
        delivery_document_id: UUID,
        employee_id: UUID,
    ) -> str:
        """Продлевает блокировку владельца и возвращает его имя."""

    @abstractmethod
    async def release_edit_lock(
        self,
        *,
        delivery_document_id: UUID,
        employee_id: UUID,
    ) -> None:
        """Освобождает блокировку владельца."""

    @abstractmethod
    async def validate_active_assignments(
        self,
        *,
        document_type: str,
        planned_date: date,
        driver_id: UUID | None,
        car_id: UUID | None,
    ) -> None:
        """Проверяет допустимость водителя и автомобиля при назначении."""
