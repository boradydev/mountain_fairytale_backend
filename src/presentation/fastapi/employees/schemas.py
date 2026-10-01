from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from src.presentation.fastapi.common.schemas import BaseSchema


class CredsReq(BaseSchema):
    username: Annotated[str, Field(min_length=0, max_length=50)]
    password: Annotated[str, Field(min_length=0, max_length=50)]


class RefreshTokenReq(BaseSchema):
    refresh_token: str


class AuthTokensResp(BaseSchema):
    access_token: str
    refresh_token: str


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


class UpdateEmployeeReq(BaseSchema):
    username: Annotated[str | None, Field(min_length=1, max_length=50)] = None


class ChangeEmployeePasswordReq(BaseSchema):
    password: Annotated[str, Field(min_length=0, max_length=50)]


class AccessTokenPyload(BaseSchema):
    employee_id: str
    role: str
    exp: datetime


class RefreshTokenPyload(BaseSchema):
    employee_id: str
    exp: datetime