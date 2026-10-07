from dataclasses import dataclass
from uuid import UUID

from src.feat.sales_rep.app.abcs.sales_rep_uow_abcs import ISalesRepresentativesUOW
from src.feat.sales_rep.domain.sales_rep_entities import SalesRepresentative


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateSalesRepresentativeDTO:
    actor_id: UUID
    name: str
    phone: str
    commission_percent: float


class CreateSalesRepresentativeUseCase:
    def __init__(
        self,
        uow: ISalesRepresentativesUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: CreateSalesRepresentativeDTO,
    ) -> SalesRepresentative:
        async with self._uow as uow:
            rep = SalesRepresentative.create(
                actor_id=dto.actor_id,
                name=dto.name,
                phone=dto.phone,
                commission_percent=dto.commission_percent,
            )

            await uow.sales_representatives.add(rep)

            await uow.commit(
                events=rep.pull_events(),
            )

            return rep
