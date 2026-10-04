from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request, Response

from src.api.fastapi.auth.abcs.tokens import IAuthTokenManager
from src.api.fastapi.auth.auth_schemas import AccessTokenPyload
from src.api.fastapi.common.api_excs import UnauthorizedException
from src.app.employees.usecases.get import GetEmployeeDTO
from src.domain.auth.auth_excs import InvalidCredentialsException
from src.domain.employees.entities import Employee
from src.infra.factories.app_context import AppContext
from src.infra.web.fastapi.cookies import AuthTokenManager


def get_app_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


Context = Annotated[AppContext, Depends(get_app_ctx)]


def get_auth_token_manager(
    ctx: Context,
    request: Request,
    response: Response,
) -> IAuthTokenManager:
    return AuthTokenManager(
        request=request,
        response=response,
        settings=ctx.token_settings,
    )


AuthTokenManagerDep = Annotated[IAuthTokenManager, Depends(get_auth_token_manager)]


def verify_access_token(
    auth_token_manager: AuthTokenManagerDep,
) -> str:
    access_token = auth_token_manager.access_token_from_header

    if access_token is None:
        access_token = auth_token_manager.access_token_from_cookie

    if access_token is None:
        raise UnauthorizedException

    return access_token


def get_access_token_pyload(
    access_token: Annotated[str, Depends(verify_access_token)],
    ctx: Context,
) -> AccessTokenPyload:
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
