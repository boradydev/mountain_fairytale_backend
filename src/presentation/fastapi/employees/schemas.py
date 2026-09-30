from typing import Annotated

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
    username: str


class EmployeesResp(BaseSchema):
    employees: list[EmployeeResp]


class AccessTokenPyload(BaseSchema):
    employee_id: str
    role: str

class RefreshTokenPyload(BaseSchema):
    employee_id: str