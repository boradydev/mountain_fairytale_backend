from dataclasses import dataclass

from src.feat.delivery_document.app.abcs.delivery_document_uow_abcs import IDeliveryDocumentsUOW
from src.feat.delivery_document.domain.delivery_day_models import DeliveryDay


@dataclass(frozen=True, slots=True, kw_only=True)
class GetDeliveryDaysDTO:
    offset: int = 0
    limit: int = 100


class GetDeliveryDaysUseCase:
    def __init__(self, uow: IDeliveryDocumentsUOW) -> None:
        self._uow = uow

    async def execute(self, dto: GetDeliveryDaysDTO) -> tuple[list[DeliveryDay], int]:
        async with self._uow as uow:
            return await uow.delivery_documents.get_days(offset=dto.offset, limit=dto.limit)
