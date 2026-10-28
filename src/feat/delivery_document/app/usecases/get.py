from dataclasses import dataclass
from uuid import UUID

from src.feat.delivery_document.app.abcs.delivery_document_uow_abcs import IDeliveryDocumentsUOW
from src.feat.delivery_document.domain.delivery_document_entities import DeliveryDocument
from src.feat.delivery_document.domain.delivery_document_excs import DeliveryDocumentNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class GetDeliveryDocumentDTO:
    delivery_document_id: UUID
    document_type: str
    by_creation_request: bool = False


class GetDeliveryDocumentUseCase:
    def __init__(self, uow: IDeliveryDocumentsUOW) -> None:
        self._uow = uow

    async def execute(self, dto: GetDeliveryDocumentDTO) -> DeliveryDocument:
        async with self._uow as uow:
            if dto.by_creation_request:
                document = await uow.delivery_documents.get_by_creation_request(
                    dto.delivery_document_id, document_type=dto.document_type
                )
            else:
                document = await uow.delivery_documents.get_by_id(
                    dto.delivery_document_id,
                    document_type=dto.document_type,
                )
            if document is None:
                raise DeliveryDocumentNotFoundException(delivery_document_id=dto.delivery_document_id)
            return document
