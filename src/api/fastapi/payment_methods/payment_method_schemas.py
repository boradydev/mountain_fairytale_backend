from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from src.api.fastapi.common.patch_schema import create_patch_schema_for_domain
from src.api.fastapi.common.schemas import BaseSchema
from src.domain.payment_methods.payment_method_entities import PaymentMethod


class PaymentMethodResp(BaseSchema):
    payment_method_id: UUID
    name: str
    created_at: datetime
    is_active: bool


class PaymentMethodsResp(BaseSchema):
    payment_methods: list[PaymentMethodResp]


class CreatePaymentMethodReq(BaseSchema):
    name: Annotated[str, Field(min_length=1, max_length=120)]


class UpdatePaymentMethodReq(create_patch_schema_for_domain(
    PaymentMethod, 
    exclude_fields={"payment_method_id", "created_at"}
)):
    """
    PATCH schema for PaymentMethod.
    """
