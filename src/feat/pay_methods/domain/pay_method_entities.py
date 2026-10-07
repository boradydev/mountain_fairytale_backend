from datetime import datetime
from typing import Any, Self
from uuid import UUID

from sqlalchemy import DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.uuid7 import uuid7
from src.common.domain.entities import BaseEntity


class PaymentMethod(BaseEntity):
    __tablename__ = "pay_methods"

    payment_method_id: Mapped[UUID] = mapped_column(primary_key=True)
    
    UQ_NAME = "payment_methods_name_key"
    name: Mapped[str] = mapped_column(
        Text, 
        UniqueConstraint(name=UQ_NAME)
    )
    
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    _ALLOWED_UPDATE_FIELDS = {
        "name",
        "is_active",
    }

    @classmethod
    def create(
        cls,
        *,
        actor_id: UUID,
        name: str,
    ) -> Self:
        method = cls(
            payment_method_id=uuid7(),
            name=name,
            is_active=True,
            created_at=datetime.now(),
        )

        method._add_event(
            events.CreatePaymentMethodEvent(
                actor_id=actor_id,
                payment_method_id=method.payment_method_id,
            ),
        )

        return method

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
            events.UpdatePaymentMethodEvent(
                actor_id=actor_id,
                payment_method_id=self.payment_method_id,
                changes=changes,
            ),
        )
