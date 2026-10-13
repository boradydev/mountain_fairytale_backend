from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliveryDayProduct:
    product_id: UUID
    product_name: str
    quantity: int


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliveryDay:
    planned_date: date
    delivery_points_count: int
    pickup_points_count: int
    products: list[DeliveryDayProduct]
    total_amount: Decimal


@dataclass(frozen=True, slots=True, kw_only=True)
class DayDocumentItem:
    product_id: UUID
    product_name: str
    quantity: int
    price: float


@dataclass(frozen=True, slots=True, kw_only=True)
class DayDocumentPoint:
    point_id: UUID
    client_id: UUID
    client_name: str
    phone: str
    address: str
    default_payment_method_id: UUID | None
    default_payment_method_name: str | None
    sales_representative_id: UUID | None
    sales_representative_name: str | None
    position: int
    items: list[DayDocumentItem]


@dataclass(frozen=True, slots=True, kw_only=True)
class DayDocument:
    delivery_document_id: UUID
    created_at: datetime
    planned_date: date
    is_active: bool
    points: list[DayDocumentPoint]


@dataclass(frozen=True, slots=True, kw_only=True)
class DayDeliveryRouteSheet(DayDocument):
    document_type: Literal["deliveryRouteSheet"]
    driver_id: UUID
    driver_name: str
    car_id: UUID
    car_model_and_number: str
    start_mileage: float
    end_mileage: float | None


@dataclass(frozen=True, slots=True, kw_only=True)
class DayPickupSheet(DayDocument):
    document_type: Literal["pickupSheet"]


type DayDocumentRecord = DayDeliveryRouteSheet | DayPickupSheet
