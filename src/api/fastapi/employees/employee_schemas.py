from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from src.api.fastapi.common.patch_schema import create_patch_schema_for_domain
from src.api.fastapi.common.schemas import BaseSchema
from src.domain.employees.employee_entities import Employee


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


class UpdateEmployeeReq(create_patch_schema_for_domain(Employee)):
    """
    PATCH schema for Employee.
    Allowed fields: username, is_active.
    All fields are optional, but non-nullable.
    """


class ChangeEmployeePasswordReq(BaseSchema):
    password: Annotated[str, Field(min_length=0, max_length=50)]
