from dataclasses import dataclass

from src.feat.clients.app.abcs.client_uow_abcs import IClientsUOW
from src.feat.clients.domain.client_entities import Client


@dataclass(frozen=True, slots=True, kw_only=True)
class GetClientsDTO:
    include_deactivated: bool
    offset: int
    limit: int


class GetClientsUseCase:
    def __init__(self, uow: IClientsUOW) -> None:
        self._uow = uow

    async def execute(self, dto: GetClientsDTO) -> tuple[list[Client], int]:
        async with self._uow as uow:
            return await uow.clients.get_all(
                include_deactivated=dto.include_deactivated,
                offset=dto.offset,
                limit=dto.limit,
            )
