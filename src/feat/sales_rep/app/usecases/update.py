from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.feat.sales_rep.app.abcs.sales_rep_uow_abcs import ISalesRepresentativesUOW
from src.domain.sales_representatives.sales_representative_entities import SalesRepresentative
from src.feat.sales_rep.domain.sales_rep_excs import SalesRepresentativeNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateSalesRepresentativeDTO:
    actor_id: UUID
    sales_representative_id: UUID
    payload: dict[str, Any]


class UpdateSalesRepresentativeUseCase:
    def __init__(
        self,
        uow: ISalesRepresentativesUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: UpdateSalesRepresentativeDTO,
    ) -> SalesRepresentative:
        async with self._uow as uow:
            rep = await uow.sales_representatives.get_by_id(dto.sales_representative_id)

            if rep is None:
                raise SalesRepresentativeNotFoundException(
                    sales_representative_id=dto.sales_representative_id,
                )

            rep.update(
                actor_id=dto.actor_id,
                **dto.payload,
            )

            await uow.sales_representatives.update(rep)

            await uow.commit(
                events=rep.pull_events(),
            )

            return rep
