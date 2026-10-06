from datetime import datetime
from typing import Any, Self
from uuid import UUID

from sqlalchemy import DateTime, Float, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.uuid7 import uuid7
from src.domain.products import events
from src.domain.common.entities import BaseEntity


class Product(BaseEntity):
    __tablename__ = "products"

    product_id: Mapped[UUID] = mapped_column(primary_key=True)
    
    UQ_NAME = "products_name_key"
    name: Mapped[str] = mapped_column(
        Text, 
        UniqueConstraint(name=UQ_NAME)
    )
    
    base_price: Mapped[float] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    _ALLOWED_UPDATE_FIELDS = {
        "name",
        "base_price",
        "is_active",
    }

    @classmethod
    def create(
        cls,
        *,
        actor_id: UUID,
        name: str,
        base_price: float,
    ) -> Self:
        product = cls(
            product_id=uuid7(),
            name=name,
            base_price=base_price,
            is_active=True,
            created_at=func.now(),
        )

        product._add_event(
            events.CreateProductEvent(
                actor_id=actor_id,
                product_id=product.product_id,
            ),
        )

        return product

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
            events.UpdateProductEvent(
                actor_id=actor_id,
                product_id=self.product_id,
                changes=changes,
            ),
        )
