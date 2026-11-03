from dataclasses import dataclass
from datetime import date

from src.feat.delivery_document.app.abcs.delivery_document_uow_abcs import IDeliveryDocumentsUOW
from src.feat.delivery_document.domain.delivery_history_models import HistoryDocument, validate_history_period


@dataclass(frozen=True, slots=True, kw_only=True)
class GetDeliveryHistoryDTO:
    date_from: date
    date_to: date
    search: str = ""
    include_cancelled: bool = False
    offset: int = 0
    limit: int = 25


class GetDeliveryHistoryUseCase:
    def __init__(self, uow: IDeliveryDocumentsUOW) -> None:
        self._uow = uow

    async def execute(self, dto: GetDeliveryHistoryDTO) -> tuple[list[HistoryDocument], int]:
        validate_history_period(dto.date_from, dto.date_to)
        async with self._uow as uow:
            return await uow.delivery_documents.get_history(
                date_from=dto.date_from,
                date_to=dto.date_to,
                search=dto.search.strip(),
                include_cancelled=dto.include_cancelled,
                offset=dto.offset,
                limit=dto.limit,
            )
