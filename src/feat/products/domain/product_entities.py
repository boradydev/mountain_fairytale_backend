from datetime import datetime
from decimal import Decimal
from typing import Any, Self
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.common.domain.entities import BaseEntity
from src.core.uuid7 import uuid7
from src.feat.products.domain.product_events import CreateProductEvent, UpdateProductEvent
from src.feat.products.domain.product_excs import ProductDomainUpdateException


class Product(BaseEntity):
    _EVENT_FIELDS = {"name", "is_active", "base_price", "is_free_price"}
    _EVENT_SUBJECT_TYPE = "product"
    _EVENT_ID_FIELD = "product_id"
    _EVENT_NAME_FIELDS = ("name",)

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("NOT is_free_price OR base_price = 0", name="products_free_price_base_price_check"),
    )

    product_id: Mapped[UUID] = mapped_column(primary_key=True)

    UQ_NAME = "products_name_key"
    name: Mapped[str] = mapped_column(Text, UniqueConstraint(name=UQ_NAME))

    base_price: Mapped[Decimal] = mapped_column(Numeric)
    is_free_price: Mapped[bool] = mapped_column(default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    _ALLOWED_UPDATE_FIELDS = {
        "name",
        "base_price",
        "is_free_price",
        "is_active",
    }

    @classmethod
    def create(
        cls,
        *,
        actor_id: UUID,
        name: str,
        base_price: Decimal,
        is_free_price: bool = False,
    ) -> Self:
        if is_free_price:
            base_price = Decimal("0")
        product = cls(
            product_id=uuid7(),
            name=name,
            base_price=base_price,
            is_free_price=is_free_price,
            is_active=True,
            created_at=datetime.now(),
        )

        product._add_event(
            CreateProductEvent(
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
        if payload.get("is_free_price", self.is_free_price):
            payload["base_price"] = Decimal("0")
        self._validate_update(payload)

        changes = self._apply_update_changes(
            payload=payload,
            allowed_fields=self._ALLOWED_UPDATE_FIELDS,
        )

        if not changes:
            return

        self._add_event(
            UpdateProductEvent(
                actor_id=actor_id,
                product_id=self.product_id,
                changes=changes,
            ),
        )

    def _validate_update(self, payload: dict[str, Any]) -> None:
        price = payload.get("base_price")
        if price is not None and (price < 0 or price > 1_000_000_000):
            raise ProductDomainUpdateException(
                field="base_price",
                message="base_price must be between 0 and 1,000,000,000",
            )
