from datetime import datetime
from typing import Any, Self
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.domain.entities import BaseEntity
from src.core.uuid7 import uuid7
from src.feat.sales_rep.domain.sales_rep_entities import SalesRepresentative


class Client(BaseEntity):
    __tablename__ = "clients"

    UQ_PHONE = "clients_phone_key"
    FK_SALES_REPRESENTATIVE = "clients_sales_representative_id_fkey"
    FK_PAYMENT_METHOD = "clients_default_payment_method_id_fkey"

    client_id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    phone: Mapped[str] = mapped_column(Text)
    address: Mapped[str] = mapped_column(Text)
    last_delivery_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_delivery_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sleeping_threshold_days: Mapped[int] = mapped_column(Integer)
    sales_representative_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "sales_representatives.sales_representative_id",
            name=FK_SALES_REPRESENTATIVE,
        ),
        nullable=True,
    )
    default_payment_method_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "payment_methods.payment_method_id",
            name=FK_PAYMENT_METHOD,
        ),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    sales_representative: Mapped[SalesRepresentative | None] = relationship(
        lazy="joined",
    )

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

    @property
    def sales_representative_name(self) -> str | None:
        if self.sales_representative is None:
            return None

        return self.sales_representative.name

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
            last_delivery_date=None,
            last_delivery_quantity=None,
            cooldown_until=cooldown_until,
            sleeping_threshold_days=sleeping_threshold_days,
            sales_representative_id=sales_representative_id,
            default_payment_method_id=default_payment_method_id,
            is_active=True,
            created_at=datetime.now(),
        )

        from src.feat.clients.domain.client_events import CreateClientEvent

        client._add_event(
            CreateClientEvent(
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

        from src.feat.clients.domain.client_events import UpdateClientEvent

        self._add_event(
            UpdateClientEvent(
                actor_id=actor_id,
                client_id=self.client_id,
                changes=changes,
            ),
        )
