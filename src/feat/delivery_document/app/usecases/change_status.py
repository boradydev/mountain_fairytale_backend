from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.feat.delivery_document.app.abcs.delivery_document_uow_abcs import (
    IDeliveryDocumentsUOW,
)
from src.feat.delivery_document.domain.delivery_document_entities import (
    DeliveryDocument,
)
from src.feat.delivery_document.domain.delivery_document_excs import (
    DeliveryDocumentEditLockNotFoundException,
    DeliveryDocumentLockedException,
    DeliveryDocumentNotFoundException,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangeDeliveryDocumentStatusDTO:
    actor_id: UUID
    delivery_document_id: UUID
    document_type: str


class CancelDeliveryDocumentUseCase:
    def __init__(self, uow: IDeliveryDocumentsUOW) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: ChangeDeliveryDocumentStatusDTO,
    ) -> DeliveryDocument:
        async with self._uow as uow:
            document = await uow.delivery_documents.get_by_id(
                dto.delivery_document_id,
                document_type=dto.document_type,
            )
            if document is None:
                raise DeliveryDocumentNotFoundException(
                    delivery_document_id=dto.delivery_document_id,
                )

            lock = await uow.delivery_documents.get_edit_lock(
                dto.delivery_document_id,
            )
            now = datetime.now(UTC).replace(tzinfo=None)

            if lock is None or lock.expires_at <= now:
                raise DeliveryDocumentEditLockNotFoundException(
                    delivery_document_id=dto.delivery_document_id,
                )
            if lock.employee_id != dto.actor_id:
                raise DeliveryDocumentLockedException(
                    delivery_document_id=dto.delivery_document_id,
                    owner_name=lock.employee.username,
                )

            document.cancel(actor_id=dto.actor_id)
            await uow.delivery_documents.update(document)
            await uow.commit(events=document.pull_events())
            return document


class RestoreDeliveryDocumentUseCase:
    def __init__(self, uow: IDeliveryDocumentsUOW) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: ChangeDeliveryDocumentStatusDTO,
    ) -> DeliveryDocument:
        async with self._uow as uow:
            document = await uow.delivery_documents.get_by_id(
                dto.delivery_document_id,
                document_type=dto.document_type,
            )
            if document is None:
                raise DeliveryDocumentNotFoundException(
                    delivery_document_id=dto.delivery_document_id,
                )

            lock = await uow.delivery_documents.get_edit_lock(
                dto.delivery_document_id,
            )
            now = datetime.now(UTC).replace(tzinfo=None)
            if (
                lock is not None
                and lock.expires_at > now
                and lock.employee_id != dto.actor_id
            ):
                raise DeliveryDocumentLockedException(
                    delivery_document_id=dto.delivery_document_id,
                    owner_name=lock.employee.username,
                )

            document.restore(actor_id=dto.actor_id)
            await uow.delivery_documents.update(document)
            await uow.commit(events=document.pull_events())
            return document
