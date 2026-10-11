from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from src.common.api.schemas import BaseSchema


class CredsReq(BaseSchema):
    username: Annotated[str, Field(min_length=0, max_length=50)]
    password: Annotated[str, Field(min_length=0, max_length=50)]


class RefreshTokenReq(BaseSchema):
    refresh_token: str | None = None


class AuthTokensResp(BaseSchema):
    access_token: str
    refresh_token: str


class EmployeeTokenPayload(BaseSchema):
    employee_id: str

    @field_validator("employee_id")
    @classmethod
    def validate_employee_id(cls, value: str) -> str:
        return str(UUID(value))


class AccessTokenPyload(EmployeeTokenPayload):
    role: str
    token_type: Literal["access"]
    exp: datetime


class RefreshTokenPyload(EmployeeTokenPayload):
    token_type: Literal["refresh"]
    exp: datetime
