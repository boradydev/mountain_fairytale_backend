from dataclasses import dataclass
from datetime import date
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
