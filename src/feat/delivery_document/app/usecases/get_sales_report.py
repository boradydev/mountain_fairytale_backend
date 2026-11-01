from dataclasses import dataclass
from datetime import date

from src.feat.delivery_document.app.abcs.delivery_document_uow_abcs import IDeliveryDocumentsUOW
from src.feat.delivery_document.domain.sales_report_models import SalesReport


@dataclass(frozen=True, slots=True, kw_only=True)
class GetSalesReportDTO:
    date_from: date
    date_to: date


class GetSalesReportUseCase:
    def __init__(self, uow: IDeliveryDocumentsUOW) -> None:
        self._uow = uow

    async def execute(self, dto: GetSalesReportDTO) -> SalesReport:
        async with self._uow as uow:
            return await uow.delivery_documents.get_sales_report(
                date_from=dto.date_from,
                date_to=dto.date_to,
            )
