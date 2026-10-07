from dataclasses import dataclass

from src.app.sales_representatives.abcs.uow import ISalesRepresentativesUOW
from src.domain.sales_representatives.sales_representative_entities import SalesRepresentative


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckSalesRepresentativeDuplicateDTO:
    name: str
    phone: str


class CheckSalesRepresentativeDuplicateUseCase:
    def __init__(
        self,
        uow: ISalesRepresentativesUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: CheckSalesRepresentativeDuplicateDTO,
    ) -> SalesRepresentative | None:
        async with self._uow as uow:
            return await uow.sales_representatives.search_by_fuzzy(
                name=dto.name,
                phone=dto.phone,
            )
