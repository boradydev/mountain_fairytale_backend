from dataclasses import dataclass
from uuid import UUID

from src.feat.sales_rep.app.abcs.sales_rep_uow_abcs import ISalesRepresentativesUOW
from src.feat.sales_rep.domain.sales_rep_entities import SalesRepresentative
from src.feat.sales_rep.domain.sales_rep_excs import SalesRepresentativeNotFoundException


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
