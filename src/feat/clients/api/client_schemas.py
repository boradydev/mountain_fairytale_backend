from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from src.common.api.patch_schema import BasePatchSchema
from src.common.api.schemas import BaseSchema
from src.feat.clients.domain.client_entities import Client


class ClientResp(BaseSchema):
    client_id: UUID
    name: str
    phone: str
    address: str
    sleeping_threshold_days: int

    last_delivery_date: datetime | None
    last_delivery_quantity: int | None
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
    name: Annotated[str, Field(min_length=1, max_length=120)]
    phone: Annotated[str, Field(min_length=1, max_length=32)]
    address: Annotated[str, Field(min_length=1, max_length=500)]
    cooldown_until: datetime | None = None
    sleeping_threshold_days: Annotated[int, Field(ge=0, le=3650)]
    sales_representative_id: UUID | None = None
    default_payment_method_id: UUID | None = None


class UpdateClientReq(BasePatchSchema):
    __entity__ = Client

    name: Annotated[str | None, Field(default=None, min_length=1, max_length=120)]
    phone: Annotated[str | None, Field(default=None, min_length=1, max_length=32)]
    address: Annotated[str | None, Field(default=None, min_length=1, max_length=500)]
    cooldown_until: datetime | None = None
    sleeping_threshold_days: Annotated[int | None, Field(default=None, ge=0, le=3650)]
    sales_representative_id: UUID | None = None
    default_payment_method_id: UUID | None = None
    is_active: bool | None = None
