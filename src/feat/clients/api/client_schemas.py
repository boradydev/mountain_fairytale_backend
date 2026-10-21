from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, ConfigDict, Field, StringConstraints, model_validator

from src.common.api.patch_schema import BasePatchSchema
from src.common.api.schemas import BaseSchema
from src.feat.clients.api.address_schemas import DeliveryAddress
from src.feat.clients.domain.client_entities import Client


def _validate_local_datetime(value: datetime) -> datetime:
    if value.tzinfo is not None:
        raise ValueError("Use server-local datetime without a timezone offset.")
    return value


ServerLocalDateTime = Annotated[datetime, AfterValidator(_validate_local_datetime)]


class LastOrderItemResp(BaseSchema):
    product_id: UUID
    product_name: str
    quantity: int


class LastOrderResp(BaseSchema):
    date: date
    fulfillment_types: list[Literal["delivery", "pickup"]]
    items: list[LastOrderItemResp]


class ClientResp(BaseSchema):
    client_id: UUID
    name: str
    phone: str
    address: str
    delivery_address: DeliveryAddress | None
    delivery_details: str
    sleeping_threshold_days: int

    last_delivery_date: datetime | None
    last_delivery_quantity: int | None
    last_order: LastOrderResp | None = None
    cooldown_until: datetime | None

    sales_representative_id: UUID | None
    sales_representative_name: str | None

    default_payment_method_id: UUID | None
    default_payment_method_name: str | None

    created_at: datetime
    is_active: bool


class ClientsResp(BaseSchema):
    clients: list[ClientResp]


class CreateClientReq(BaseSchema):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=120)]
    phone: Annotated[str, Field(min_length=1, max_length=32)]
    address: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)] = ""
    delivery_address: DeliveryAddress | None = None
    delivery_details: Annotated[str, Field(max_length=500)] = ""
    cooldown_until: ServerLocalDateTime | None = None
    sleeping_threshold_days: Annotated[int, Field(ge=0, le=3650)]
    sales_representative_id: UUID | None = None
    default_payment_method_id: UUID | None = None

    @model_validator(mode="after")
    def resolve_address(self):
        if self.delivery_address is not None:
            self.address = self.delivery_address.formatted
        if not self.address:
            raise ValueError("Address is required")
        return self


class UpdateClientReq(BasePatchSchema):
    model_config = ConfigDict(extra="forbid")

    __entity__ = Client

    name: Annotated[str | None, Field(default=None, min_length=1, max_length=120)]
    phone: Annotated[str | None, Field(default=None, min_length=1, max_length=32)]
    delivery_address: DeliveryAddress | None = None
    address: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)] = None
    delivery_details: Annotated[str | None, Field(max_length=500)] = None
    cooldown_until: ServerLocalDateTime | None = None
    sleeping_threshold_days: Annotated[int | None, Field(default=None, ge=0, le=3650)]
    sales_representative_id: UUID | None = None
    default_payment_method_id: UUID | None = None
    is_active: bool | None = None
