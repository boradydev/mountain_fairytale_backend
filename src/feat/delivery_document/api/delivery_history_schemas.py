from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from src.common.api.schemas import BaseSchema


class HistoryItemResp(BaseSchema):
    product_id: UUID
    product_name: str
    quantity: int
    price: Decimal
    amount: Decimal


class HistoryClientPurchaseResp(BaseSchema):
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
    items: list[HistoryItemResp]


class HistoryDocumentResp(BaseSchema):
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
    matched_clients: list[HistoryClientPurchaseResp]


class DeliveryHistoryResp(BaseSchema):
    documents: list[HistoryDocumentResp]
