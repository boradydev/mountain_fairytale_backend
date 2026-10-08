from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.feat.clients.app.abcs.client_uow_abcs import IClientsUOW
from src.feat.clients.domain.client_entities import Client
from src.feat.clients.domain.client_excs import ClientRelatedEntityNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateClientDTO:
    actor_id: UUID
    name: str
    phone: str
    address: str
    sleeping_threshold_days: int
    cooldown_until: datetime | None = None
    sales_representative_id: UUID | None = None
    default_payment_method_id: UUID | None = None


class CreateClientUseCase:
    def __init__(self, uow: IClientsUOW) -> None:
        self._uow = uow

    async def execute(self, dto: CreateClientDTO) -> Client:
        async with self._uow as uow:
            if dto.sales_representative_id is not None:
                exists = await uow.clients.sales_representative_exists(
                    dto.sales_representative_id,
                )
                if not exists:
                    raise ClientRelatedEntityNotFoundException(
                        field="sales_representative_id",
                        entity_id=dto.sales_representative_id,
                    )

            if dto.default_payment_method_id is not None:
                exists = await uow.clients.payment_method_exists(
                    dto.default_payment_method_id,
                )
                if not exists:
                    raise ClientRelatedEntityNotFoundException(
                        field="default_payment_method_id",
                        entity_id=dto.default_payment_method_id,
                    )

            client = Client.create(
                actor_id=dto.actor_id,
                name=dto.name,
                phone=dto.phone,
                address=dto.address,
                sleeping_threshold_days=dto.sleeping_threshold_days,
                cooldown_until=dto.cooldown_until,
                sales_representative_id=dto.sales_representative_id,
                default_payment_method_id=dto.default_payment_method_id,
            )
            await uow.clients.add(client)
            await uow.commit(events=client.pull_events())
            return client
