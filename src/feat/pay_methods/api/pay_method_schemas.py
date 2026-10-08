from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from src.common.api.patch_schema import BasePatchSchema
from src.common.api.schemas import BaseSchema
from src.feat.pay_methods.domain.pay_method_entities import PaymentMethod


class PaymentMethodResp(BaseSchema):
    payment_method_id: UUID
    name: str
    created_at: datetime
    is_active: bool


class PaymentMethodsResp(BaseSchema):
    payment_methods: list[PaymentMethodResp]


class CreatePaymentMethodReq(BaseSchema):
    name: Annotated[str, Field(min_length=1, max_length=120)]


class UpdatePaymentMethodReq(BasePatchSchema):
    __entity__ = PaymentMethod

    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None
