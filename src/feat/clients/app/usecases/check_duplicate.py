from dataclasses import dataclass

from src.feat.clients.app.abcs.client_uow_abcs import IClientsUOW
from src.feat.clients.domain.client_entities import Client


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckClientDuplicateDTO:
    name: str
    phone: str
    address: str


class CheckClientDuplicateUseCase:
    def __init__(self, uow: IClientsUOW) -> None:
        self._uow = uow

    async def execute(self, dto: CheckClientDuplicateDTO) -> Client | None:
        async with self._uow as uow:
            return await uow.clients.search_duplicate(
                name=dto.name,
                phone=dto.phone,
                address=dto.address,
            )
