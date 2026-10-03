from typing import Annotated
from uuid import UUID

from pydantic import Field

from src.api.fastapi.common.schemas import BaseSchema


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


class UpdateCarReq(BaseSchema):
    model: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    number: Annotated[str | None, Field(min_length=1, max_length=30)] = None
    current_mileage: Annotated[float | None, Field(ge=0)] = None
