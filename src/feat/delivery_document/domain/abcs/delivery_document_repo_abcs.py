from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from src.feat.delivery_document.domain.delivery_document_entities import DeliveryDocument, EditLock


class IDeliveryDocumentsRepository(ABC):
    @abstractmethod
    async def add(self, document: DeliveryDocument) -> None: ...

    @abstractmethod
    async def update(self, document: DeliveryDocument) -> None: ...

    @abstractmethod
    async def get_by_id(self, delivery_document_id: UUID, *, document_type: str,
                        for_update: bool = False) -> DeliveryDocument | None: ...

    @abstractmethod
    async def get_all(self, *, document_type: str, include_cancelled: bool,
                      offset: int, limit: int) -> tuple[list[DeliveryDocument], int]: ...

    @abstractmethod
    async def get_edit_lock(self, delivery_document_id: UUID) -> EditLock | None: ...

    @abstractmethod
    async def acquire_edit_lock(self, *, delivery_document_id: UUID, employee_id: UUID) -> str: ...

    @abstractmethod
    async def renew_edit_lock(self, *, delivery_document_id: UUID, employee_id: UUID) -> str: ...

    @abstractmethod
    async def release_edit_lock(self, *, delivery_document_id: UUID, employee_id: UUID) -> None: ...

    @abstractmethod
    async def validate_active_assignments(self, *, document_type: str, planned_date: date,
                                          driver_id: UUID | None, car_id: UUID | None) -> None: ...

    @abstractmethod
    async def validate_references(self, document: DeliveryDocument) -> None: ...
