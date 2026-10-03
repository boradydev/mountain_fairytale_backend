from types import NoneType

from fastapi import APIRouter, Request, Response, status

from src.app.employees.usecases.change_password import (
    ChangeEmployeePasswordDTO,
)
from src.domain.employees.employee_excs import EmployeeNotFoundException
from src.infra.services.token.settings import JwtSettings
from src.infra.web.fastapi.cookies import AuthTokenManager
from src.api.fastapi.common.api_excs import UnauthorizedException
from src.api.fastapi.common.deps import (
    AccessTokenPayloadDep,
    Context,
)
from src.api.fastapi.common.excs_handlers import map_exceptions_to_responses
from src.api.fastapi.common.schemas import StdResponse
from src.api.fastapi.employees.schemas import (
    ChangeEmployeePasswordReq,
)


me_router = APIRouter(
    prefix="/me",
    tags=["Текущий пользователь"],
)


@me_router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
    responses=map_exceptions_to_responses(UnauthorizedException),
)
async def logout(
    request: Request,
    response: Response,
    _: AccessTokenPayloadDep,
) -> StdResponse[NoneType]:
    cookie_manager = AuthTokenManager(
        request=request,
        response=response,
        settings=JwtSettings(),
    )

    cookie_manager.delete_auth_cookies()

    return StdResponse(
        message="Выход выполнен.",
    )


@me_router.put(
    "/change-password",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
    responses=map_exceptions_to_responses(UnauthorizedException, EmployeeNotFoundException),
)
async def change_password(
    body: ChangeEmployeePasswordReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[NoneType]:
    from uuid import UUID

    await ctx.employees_use_cases.change_employee_password().execute(
        ChangeEmployeePasswordDTO(
            actor_id=UUID(access_token_payload.employee_id),
            employee_id=UUID(access_token_payload.employee_id),
            password=body.password,
        ),
    )

    return StdResponse(
        message="Пароль изменён.",
    )
