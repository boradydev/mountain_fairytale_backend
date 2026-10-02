from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from src.presentation.fastapi.common.schemas import BaseSchema


class CredsReq(BaseSchema):
    username: Annotated[str, Field(min_length=0, max_length=50)]
    password: Annotated[str, Field(min_length=0, max_length=50)]


class RefreshTokenReq(BaseSchema):
    refresh_token: str | None = None


class AuthTokensResp(BaseSchema):
    access_token: str
    refresh_token: str


class AccessTokenPyload(BaseSchema):
    employee_id: str
    role: str
    token_type: Literal["access"]
    exp: datetime


class RefreshTokenPyload(BaseSchema):
    employee_id: str
    token_type: Literal["refresh"]
    exp: datetime
