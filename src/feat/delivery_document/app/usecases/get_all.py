from dataclasses import dataclass

from src.feat.delivery_document.app.abcs.delivery_document_uow_abcs import (
    IDeliveryDocumentsUOW,
)
from src.feat.delivery_document.domain.delivery_document_entities import (
    DeliveryDocument,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class GetDeliveryDocumentsDTO:
    document_type: str
    include_cancelled: bool
    offset: int
    limit: int


class GetDeliveryDocumentsUseCase:
    def __init__(self, uow: IDeliveryDocumentsUOW) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: GetDeliveryDocumentsDTO,
    ) -> tuple[list[DeliveryDocument], int]:
        async with self._uow as uow:
            return await uow.delivery_documents.get_all(
                document_type=dto.document_type,
                include_cancelled=dto.include_cancelled,
                offset=dto.offset,
                limit=dto.limit,
            )
