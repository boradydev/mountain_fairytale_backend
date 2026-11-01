from datetime import date
from decimal import Decimal
from uuid import UUID

from src.common.api.schemas import BaseSchema


class SalesReportProductResp(BaseSchema):
    product_id: UUID
    product_name: str
    quantity: int
    amount: Decimal


class SalesReportPaymentMethodResp(BaseSchema):
    payment_method_id: UUID | None
    payment_method_name: str
    is_active: bool | None
    total_quantity: int
    total_amount: Decimal
    products: list[SalesReportProductResp]


class SalesReportResp(BaseSchema):
    date_from: date
    date_to: date
    total_quantity: int
    total_amount: Decimal
    payment_methods: list[SalesReportPaymentMethodResp]
