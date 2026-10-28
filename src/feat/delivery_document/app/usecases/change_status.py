from dataclasses import dataclass
from uuid import UUID

from src.feat.delivery_document.app.abcs.delivery_document_uow_abcs import IDeliveryDocumentsUOW
from src.feat.delivery_document.domain.delivery_document_entities import DeliveryDocument
from src.feat.delivery_document.domain.delivery_document_excs import (
    DeliveryDocumentLockedException,
    DeliveryDocumentNotFoundException,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangeDeliveryDocumentStatusDTO:
    actor_id: UUID
    delivery_document_id: UUID
    document_type: str


class ChangeDeliveryDocumentStatusUseCase:
    def __init__(self, uow: IDeliveryDocumentsUOW, *, restore: bool) -> None:
        self._uow = uow
        self._restore = restore

    async def execute(self, dto: ChangeDeliveryDocumentStatusDTO) -> DeliveryDocument:
        async with self._uow as uow:
            repo = uow.delivery_documents
            document = await repo.get_by_id(dto.delivery_document_id, document_type=dto.document_type, for_update=True)
            if document is None:
                raise DeliveryDocumentNotFoundException(delivery_document_id=dto.delivery_document_id)
            lock = await repo.get_edit_lock(dto.delivery_document_id)
            if lock is not None and lock.employee_id != dto.actor_id:
                raise DeliveryDocumentLockedException(
                    delivery_document_id=dto.delivery_document_id, owner_name=lock.owner_name
                )
            changed = document.is_active != self._restore
            if self._restore:
                document.restore(actor_id=dto.actor_id)
            else:
                document.cancel(actor_id=dto.actor_id)
                if lock is not None:
                    await repo.release_edit_lock(
                        delivery_document_id=dto.delivery_document_id,
                        employee_id=dto.actor_id,
                    )
            if changed:
                document.revision += 1
                document.last_operation_id = None
            await repo.update(document)
            await uow.commit(events=document.pull_aggregate_events())
            return document
