from datetime import datetime
from typing import Any, Self
from uuid import UUID

from sqlalchemy import DateTime, Float, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.uuid7 import uuid7
from src.domain.sales_representatives import events
from src.domain.common.entities import BaseEntity


class SalesRepresentative(BaseEntity):
    __tablename__ = "sales_representatives"

    sales_representative_id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    
    UQ_PHONE = "sales_representatives_phone_key"
    phone: Mapped[str] = mapped_column(
        Text, 
        UniqueConstraint(name=UQ_PHONE)
    )
    
    commission_percent: Mapped[float] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    _ALLOWED_UPDATE_FIELDS = {
        "name",
        "phone",
        "commission_percent",
        "is_active",
    }

    @classmethod
    def create(
        cls,
        *,
        actor_id: UUID,
        name: str,
        phone: str,
        commission_percent: float,
    ) -> Self:
        rep = cls(
            sales_representative_id=uuid7(),
            name=name,
            phone=phone,
            commission_percent=commission_percent,
            is_active=True,
            created_at=datetime.now(),
        )

        rep._add_event(
            events.CreateSalesRepresentativeEvent(
                actor_id=actor_id,
                sales_representative_id=rep.sales_representative_id,
            ),
        )

        return rep

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
            events.UpdateSalesRepresentativeEvent(
                actor_id=actor_id,
                sales_representative_id=self.sales_representative_id,
                changes=changes,
            ),
        )
