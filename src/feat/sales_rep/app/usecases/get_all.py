from dataclasses import dataclass

from src.feat.sales_rep.app.abcs.sales_rep_uow_abcs import ISalesRepresentativesUOW
from src.feat.sales_rep.domain.sales_rep_entities import SalesRepresentative


@dataclass(frozen=True, slots=True, kw_only=True)
class GetSalesRepresentativesDTO:
    include_deactivated: bool


class GetSalesRepresentativesUseCase:
    def __init__(
        self,
        uow: ISalesRepresentativesUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: GetSalesRepresentativesDTO,
    ) -> list[SalesRepresentative]:
        async with self._uow as uow:
            return await uow.sales_representatives.get_all(
                include_deactivated=dto.include_deactivated,
            )
