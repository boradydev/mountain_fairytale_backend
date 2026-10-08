from dataclasses import dataclass
from uuid import UUID

from src.feat.clients.api.client_schemas import UpdateClientReq
from src.feat.clients.app.abcs.client_uow_abcs import IClientsUOW
from src.feat.clients.domain.client_entities import Client
from src.feat.clients.domain.client_excs import (
    ClientNotFoundException,
    ClientRelatedEntityNotFoundException,
)


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

            sales_representative_id = changes.get("sales_representative_id")
            if sales_representative_id is not None:
                exists = await uow.clients.sales_representative_exists(
                    sales_representative_id,
                )
                if not exists:
                    raise ClientRelatedEntityNotFoundException(
                        field="sales_representative_id",
                        entity_id=sales_representative_id,
                    )

            payment_method_id = changes.get("default_payment_method_id")
            if payment_method_id is not None:
                exists = await uow.clients.payment_method_exists(payment_method_id)
                if not exists:
                    raise ClientRelatedEntityNotFoundException(
                        field="default_payment_method_id",
                        entity_id=payment_method_id,
                    )

            client.update(actor_id=dto.actor_id, **changes)
            await uow.clients.update(client)
            await uow.commit(events=client.pull_events())
            return client
