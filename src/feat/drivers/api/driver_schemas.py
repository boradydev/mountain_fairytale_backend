from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from src.common.api.patch_schema import BasePatchSchema
from src.common.api.schemas import BaseSchema
from src.feat.drivers.domain.driver_entities import Driver


class DriverResp(BaseSchema):
    driver_id: UUID
    name: str
    created_at: datetime
    is_active: bool


class DriversResp(BaseSchema):
    drivers: list[DriverResp]


class CreateDriverReq(BaseSchema):
    name: Annotated[str, Field(min_length=1, max_length=120)]


class UpdateDriverReq(BasePatchSchema):
    __entity__ = Driver

    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None
