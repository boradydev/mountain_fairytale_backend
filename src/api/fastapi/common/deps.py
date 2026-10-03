from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from src.app.employees.usecases.get import GetEmployeeDTO
from src.domain.employees.entities import Employee
from src.domain.employees.employee_excs import InvalidCredentialsException
from src.infra.factories.app_context import AppContext
from src.api.fastapi.common.api_excs import UnauthorizedException
from src.api.fastapi.auth.auth_schemas import AccessTokenPyload


def get_app_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


Context = Annotated[AppContext, Depends(get_app_ctx)]


def get_access_token_pyload(
    request: Request,
    ctx: Context,
) -> AccessTokenPyload:
    authorization = request.headers.get("Authorization")

    access_token: str | None = None

    if authorization is not None:
        scheme, _, value = authorization.partition(" ")

        if scheme.lower() == "bearer" and value:
            access_token = value

    if access_token is None:
        access_token = request.cookies.get("access_token")

    if access_token is None:
        raise UnauthorizedException

    return ctx.token_service.get_payload_access_token(
        access_token=access_token,
    )


AccessTokenPayloadDep = Annotated[
    AccessTokenPyload,
    Depends(get_access_token_pyload),
]


async def get_current_employee(
    access_token_payload: AccessTokenPayloadDep,
    ctx: Context,
) -> Employee:
    employee = await ctx.employees_use_cases.get_employee().execute(
        GetEmployeeDTO(
            employee_id=UUID(access_token_payload.employee_id),
        ),
    )

    if not employee.is_active:
        raise InvalidCredentialsException

    return employee


CurrentEmployee = Annotated[
    Employee,
    Depends(get_current_employee),
]