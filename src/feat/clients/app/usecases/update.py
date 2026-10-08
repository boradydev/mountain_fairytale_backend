from dataclasses import dataclass
from uuid import UUID

from src.feat.clients.api.client_schemas import UpdateClientReq
from src.feat.clients.app.abcs.client_uow_abcs import IClientsUOW
from src.feat.clients.domain.client_entities import Client
from src.feat.clients.domain.client_excs import ClientNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateClientDTO:
    actor_id: UUID
    client_id: UUID
    payload: UpdateClientReq


class UpdateClientUseCase:
    def __init__(self, uow: IClientsUOW) -> None:
        self._uow = uow

    async def execute(self, dto: UpdateClientDTO) -> Client:
        async with self._uow as uow:
            client = await uow.clients.get_by_id(dto.client_id)
            if client is None:
                raise ClientNotFoundException(client_id=dto.client_id)

            changes = dto.payload.changes()

            client.update(actor_id=dto.actor_id, **changes)
            await uow.clients.update(client)
            await uow.commit(events=client.pull_events())
            return client
