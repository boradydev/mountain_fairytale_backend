from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from src.common.api.patch_schema import BasePatchSchema
from src.common.api.schemas import BaseSchema
from src.feat.employees.domain.employee_entities import Employee


class EmployeeResp(BaseSchema):
    employee_id: UUID
    username: str
    role: str
    is_active: bool
    created_at: datetime


class EmployeesResp(BaseSchema):
    employees: list[EmployeeResp]


class CreateEmployeeReq(BaseSchema):
    username: Annotated[str, Field(min_length=1, max_length=50)]
    password: Annotated[str, Field(min_length=0, max_length=50)]


class UpdateEmployeeReq(BasePatchSchema):
    __entity__ = Employee

    username: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None


class ChangeEmployeePasswordReq(BaseSchema):
    password: Annotated[str, Field(min_length=0, max_length=50)]
