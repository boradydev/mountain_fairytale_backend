from dataclasses import dataclass
from uuid import UUID

from src.feat.clients.app.abcs.client_uow_abcs import IClientsUOW
from src.feat.clients.domain.client_entities import Client
from src.feat.clients.domain.client_excs import ClientNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class GetClientDTO:
    client_id: UUID


class GetClientUseCase:
    def __init__(self, uow: IClientsUOW) -> None:
        self._uow = uow

    async def execute(self, dto: GetClientDTO) -> Client:
        async with self._uow as uow:
            client = await uow.clients.get_by_id(dto.client_id)
            if client is None:
                raise ClientNotFoundException(client_id=dto.client_id)
            return client
