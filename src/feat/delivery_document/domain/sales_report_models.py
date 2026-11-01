from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class SalesReportProduct:
    product_id: UUID
    product_name: str
    quantity: int
    amount: Decimal


@dataclass(frozen=True, slots=True, kw_only=True)
class SalesReportPaymentMethod:
    payment_method_id: UUID | None
    payment_method_name: str
    is_active: bool | None
    total_quantity: int
    total_amount: Decimal
    products: list[SalesReportProduct]


@dataclass(frozen=True, slots=True, kw_only=True)
class SalesReport:
    date_from: date
    date_to: date
    total_quantity: int
    total_amount: Decimal
    payment_methods: list[SalesReportPaymentMethod]
