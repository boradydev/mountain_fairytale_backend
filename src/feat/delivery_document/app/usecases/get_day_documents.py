from dataclasses import dataclass
from datetime import date

from src.feat.delivery_document.app.abcs.delivery_document_uow_abcs import IDeliveryDocumentsUOW
from src.feat.delivery_document.domain.delivery_day_models import DayDocumentRecord


@dataclass(frozen=True, slots=True, kw_only=True)
class GetDayDocumentsDTO:
    planned_date: date
    include_cancelled: bool = False


class GetDayDocumentsUseCase:
    def __init__(self, uow: IDeliveryDocumentsUOW) -> None:
        self._uow = uow

    async def execute(self, dto: GetDayDocumentsDTO) -> list[DayDocumentRecord]:
        async with self._uow as uow:
            return await uow.delivery_documents.get_day_documents(
                planned_date=dto.planned_date, include_cancelled=dto.include_cancelled
            )
