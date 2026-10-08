from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from src.common.api.patch_schema import BasePatchSchema
from src.common.api.schemas import BaseSchema
from src.feat.sales_rep.domain.sales_rep_entities import SalesRepresentative


class SalesRepresentativeResp(BaseSchema):
    sales_representative_id: UUID
    name: str
    phone: str
    commission_percent: float
    created_at: datetime
    is_active: bool


class SalesRepresentativesResp(BaseSchema):
    sales_representatives: list[SalesRepresentativeResp]


class CreateSalesRepresentativeReq(BaseSchema):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    phone: Annotated[str, Field(min_length=1, max_length=32)]
    commission_percent: Annotated[float, Field(ge=0, le=100)]


class UpdateSalesRepresentativeReq(BasePatchSchema):
    __entity__ = SalesRepresentative

    name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, min_length=1, max_length=32)
    commission_percent: float | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None
