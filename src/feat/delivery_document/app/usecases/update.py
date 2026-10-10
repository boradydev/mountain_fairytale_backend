from dataclasses import dataclass
from uuid import UUID
from typing import Any

from src.feat.delivery_document.app.abcs.delivery_document_uow_abcs import IDeliveryDocumentsUOW
from src.feat.delivery_document.domain.delivery_document_entities import DeliveryDocument
from src.feat.delivery_document.domain.delivery_document_excs import (
    DeliveryDocumentLockedException, DeliveryDocumentNotFoundException,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateDeliveryDocumentDTO:
    actor_id: UUID
    delivery_document_id: UUID
    document_type: str
    payload: Any


class UpdateDeliveryDocumentUseCase:
    def __init__(self, uow: IDeliveryDocumentsUOW) -> None:
        self._uow = uow

    async def execute(self, dto: UpdateDeliveryDocumentDTO) -> DeliveryDocument:
        async with self._uow as uow:
            repo = uow.delivery_documents
            document = await repo.get_by_id(
                dto.delivery_document_id, document_type=dto.document_type, for_update=True,
            )
            if document is None:
                raise DeliveryDocumentNotFoundException(delivery_document_id=dto.delivery_document_id)
            if not document.is_active:
                from src.feat.delivery_document.domain.delivery_document_excs import DeliveryDocumentUpdateException
                raise DeliveryDocumentUpdateException(field="is_active", message="Restore the document before editing it.")
            lock = await repo.get_edit_lock(dto.delivery_document_id)
            if lock is not None and lock.employee_id != dto.actor_id:
                raise DeliveryDocumentLockedException(
                    delivery_document_id=dto.delivery_document_id, owner_name=lock.owner_name,
                )
            document.update(actor_id=dto.actor_id, request=dto.payload)
            await repo.validate_active_assignments(
                document_type=document.document_type, planned_date=document.planned_date,
                driver_id=document.driver_id, car_id=document.car_id,
            )
            await repo.validate_references(document)
            await repo.update(document)
            events = document.pull_aggregate_events()
            loaded = await repo.get_by_id(
                document.delivery_document_id, document_type=document.document_type,
            )
            await uow.commit(events=events)
            return loaded or document
