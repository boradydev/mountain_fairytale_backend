from typing import Annotated
from uuid import UUID

from pydantic import Field

from src.common.api.patch_schema import BasePatchSchema
from src.common.api.schemas import BaseSchema
from src.feat.cars.domain.car_entities import Car


class CarResp(BaseSchema):
    car_id: UUID
    model: str
    number: str
    current_mileage: float
    is_active: bool


class CarsResp(BaseSchema):
    cars: list[CarResp]


class CreateCarReq(BaseSchema):
    model: Annotated[str, Field(min_length=1, max_length=100)]
    number: Annotated[str, Field(min_length=1, max_length=30)]
    current_mileage: Annotated[float, Field(ge=0)] = 0


class UpdateCarReq(BasePatchSchema):
    __entity__ = Car

    model: str | None = Field(default=None, min_length=1, max_length=100)
    number: str | None = Field(default=None, min_length=1, max_length=30)
    current_mileage: float | None = Field(default=None, ge=0)
    is_active: bool | None = None
