from typing import Annotated
from uuid import UUID

from pydantic import Field

from src.api.fastapi.common.patch_schema import create_patch_schema_for_domain
from src.api.fastapi.common.schemas import BaseSchema
from src.domain.cars.car_entities import Car


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


class UpdateCarReq(create_patch_schema_for_domain(Car)):
    """
    PATCH schema for Car.
    Allowed fields: model, number, current_mileage, is_active.
    All fields are optional, but non-nullable.
    """
