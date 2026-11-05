from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID


def history_last_date(start: date) -> date:
    """Inclusive last date of twelve calendar months, including leap years."""
    if start.year == date.max.year:
        return date.max
    try:
        anniversary = start.replace(year=start.year + 1)
    except ValueError:
        anniversary = date(start.year + 1, 3, 1)
    return anniversary - timedelta(days=1)


def validate_history_period(start: date, end: date) -> None:
    if end < start:
        raise ValueError("date_from must be on or before date_to.")
    if end > history_last_date(start):
        raise ValueError("History period cannot exceed twelve calendar months.")


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoryItem:
    item_id: UUID
    product_id: UUID
    product_name: str
    quantity: int
    price: Decimal
    amount: Decimal
    is_free_price: bool = False
    driver_note: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoryClientPurchase:
    is_delivered: bool
    non_delivery_reason: str
    memo: str
    point_id: UUID
    client_id: UUID
    client_name: str
    address: str
    phone: str
    payment_method_id: UUID | None
    payment_method_name: str | None
    total_amount: Decimal
    items: list[HistoryItem]


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoryDocument:
    delivery_document_id: UUID
    document_type: Literal["deliveryRouteSheet", "pickupSheet"]
    planned_date: date
    created_at: datetime
    is_active: bool
    driver_name: str | None
    car_model_and_number: str | None
    clients_count: int
    purchases_count: int
    total_amount: Decimal
    matched_clients: list[HistoryClientPurchase]


@dataclass(frozen=True, slots=True, kw_only=True)
class ClientDelivery(HistoryClientPurchase):
    client_address: str
    delivery_details: str
    sales_representative_id: UUID | None
    sales_representative_name: str | None
    delivery_document_id: UUID
    planned_date: date
    created_at: datetime
    driver_name: str | None
    car_model_and_number: str | None
    document_total_amount: Decimal
