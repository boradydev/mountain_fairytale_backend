from dataclasses import dataclass
from uuid import UUID

from src.app.sales_representatives.abcs.uow import ISalesRepresentativesUOW
from src.domain.sales_representatives.car_entities import SalesRepresentative # Ошибка в пути, исправляю на правильный
from src.domain.sales_representatives.sales_representative_entities import SalesRepresentative
from src.domain.sales_representatives.sales_representative_excs import SalesRepresentativeNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class GetSalesRepresentativeDTO:
    sales_representative_id: UUID


class GetSalesRepresentativeUseCase:
    def __init__(
        self,
        uow: ISalesRepresentativesUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: GetSalesRepresentativeDTO,
    ) -> SalesRepresentative:
        async with self._uow as uow:
            rep = await uow.sales_representatives.get_by_id(dto.sales_representative_id)

            if rep is None:
                raise SalesRepresentativeNotFoundException(
                    sales_representative_id=dto.sales_representative_id,
                )

            return rep
