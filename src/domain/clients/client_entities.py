from datetime import datetime
from typing import Any, Self
from uuid import UUID

from sqlalchemy import DateTime, Float, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.uuid7 import uuid7
from src.domain.clients import events
from src.domain.common.entities import BaseEntity


class Client(BaseEntity):
    __tablename__ = "clients"

    client_id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    phone: Mapped[str] = mapped_column(Text)
    address: Mapped[str] = mapped_column(Text)
    last_delivery_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_delivery_quantity: Mapped[int] = mapped_column(Integer, default=0)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sleeping_threshold_days: Mapped[int] = mapped_column(Integer)
    sales_representative_id: Mapped[UUID | None] = mapped_column(nullable=True)
    default_payment_method_id: Mapped[UUID | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    _ALLOWED_UPDATE_FIELDS = {
        "name",
        "phone",
        "address",
        "cooldown_until",
        "sleeping_threshold_days",
        "sales_representative_id",
        "default_payment_method_id",
        "is_active",
    }

    @classmethod
    def create(
        cls,
        *,
        actor_id: UUID,
        name: str,
        phone: str,
        address: str,
        sleeping_threshold_days: int,
        cooldown_until: datetime | None = None,
        sales_representative_id: UUID | None = None,
        default_payment_method_id: UUID | None = None,
    ) -> Self:
        client = cls(
            client_id=uuid7(),
            name=name,
            phone=phone,
            address=address,
            sleeping_threshold_days=sleeping_threshold_days,
            cooldown_until=cooldown_until,
            sales_representative_id=sales_representative_id,
            default_payment_method_id=default_payment_method_id,
            is_active=True,
            last_delivery_date=datetime.now(),
            last_delivery_quantity=0,
            created_at=func.now(),
        )

        client._add_event(
            events.CreateClientEvent(
                actor_id=actor_id,
                client_id=client.client_id,
            ),
        )

        return client

    def update(
        self,
        *,
        actor_id: UUID,
        **payload: Any,
    ) -> None:
        changes = self._apply_update_changes(
            payload=payload,
            allowed_fields=self._ALLOWED_UPDATE_FIELDS,
        )

        if not changes:
            return

        self._add_event(
            events.UpdateClientEvent(
                actor_id=actor_id,
                client_id=self.client_id,
                changes=changes,
            ),
        )
