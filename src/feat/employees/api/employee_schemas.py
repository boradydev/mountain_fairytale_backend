from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import Field, field_validator

from src.common.api.patch_schema import BasePatchSchema
from src.common.api.schemas import BaseSchema
from src.feat.employees.domain.employee_entities import Employee


class EmployeeResp(BaseSchema):
    employee_id: UUID
    username: str
    role: str
    commission_percent: float
    is_active: bool
    created_at: datetime


class EmployeesResp(BaseSchema):
    employees: list[EmployeeResp]


class CreateEmployeeReq(BaseSchema):
    username: Annotated[str, Field(min_length=1, max_length=50)]
    password: Annotated[str, Field(min_length=0, max_length=50)]
    commission_percent: Annotated[Decimal, Field(ge=0, le=100)]

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Username cannot be blank.")
        return value


class UpdateEmployeeReq(BasePatchSchema):
    __entity__ = Employee

    username: str | None = Field(default=None, min_length=1, max_length=50)
    commission_percent: Decimal | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str | None) -> str:
        if value is None or not value.strip():
            raise ValueError("Username cannot be blank or null.")
        return value


class ChangeEmployeePasswordReq(BaseSchema):
    password: Annotated[str, Field(min_length=0, max_length=50)]
