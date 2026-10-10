from dataclasses import dataclass
from uuid import UUID

from src.feat.delivery_document.app.abcs.delivery_document_uow_abcs import IDeliveryDocumentsUOW
from src.feat.delivery_document.domain.delivery_document_excs import DeliveryDocumentNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliveryDocumentEditLockDTO:
    delivery_document_id: UUID
    document_type: str
    employee_id: UUID


class DeliveryDocumentEditLockUseCase:
    def __init__(self, uow: IDeliveryDocumentsUOW, *, operation: str) -> None:
        self._uow = uow
        self._operation = operation

    async def execute(self, dto: DeliveryDocumentEditLockDTO) -> str | None:
        async with self._uow as uow:
            repo = uow.delivery_documents
            document = await repo.get_by_id(dto.delivery_document_id, document_type=dto.document_type, for_update=True)
            if document is None:
                raise DeliveryDocumentNotFoundException(delivery_document_id=dto.delivery_document_id)
            if self._operation == "acquire":
                result = await repo.acquire_edit_lock(delivery_document_id=dto.delivery_document_id, employee_id=dto.employee_id)
            elif self._operation == "renew":
                result = await repo.renew_edit_lock(delivery_document_id=dto.delivery_document_id, employee_id=dto.employee_id)
            else:
                await repo.release_edit_lock(delivery_document_id=dto.delivery_document_id, employee_id=dto.employee_id)
                result = None
            await uow.commit(events=[])
            return result
