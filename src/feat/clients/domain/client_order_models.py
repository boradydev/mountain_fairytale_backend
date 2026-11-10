from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class LastOrderItem:
    product_id: UUID
    product_name: str
    quantity: int


@dataclass(frozen=True, slots=True)
class LastOrder:
    date: date
    fulfillment_types: list[Literal["delivery", "pickup"]]
    items: list[LastOrderItem]


@dataclass(frozen=True, slots=True)
class LatestOrderItem:
    item_id: UUID
    product_id: UUID
    product_name: str
    quantity: int
    price: Decimal
    is_free_price: bool
    driver_note: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class LatestOrder:
    delivery_document_id: UUID
    point_id: UUID
    created_at: datetime
    planned_date: date
    items: list[LatestOrderItem]
    total_amount: Decimal
