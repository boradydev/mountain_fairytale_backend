from fastapi import APIRouter, status

from src.app.auth.usecases.login import LoginDTO
from src.app.auth.usecases.refresh import RefreshDTO
from src.domain.employees.excs import (
    EmployeeNotFoundByUsernameException,
    InvalidCredentialsException,
)
from src.presentation.fastapi.auth.deps import AuthTokenManagerDep
from src.presentation.fastapi.auth.excs import RefreshTokenNotFoundException, UnauthorizedException
from src.presentation.fastapi.auth.schemas import AuthTokensResp, CredsReq, RefreshTokenReq
from src.presentation.fastapi.common.deps import Context
from src.presentation.fastapi.common.handlers import map_exceptions_to_responses
from src.presentation.fastapi.common.schemas import StdResponse


auth_router = APIRouter(
    prefix="/auth",
    tags=["Авторизация"],
)


@auth_router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[AuthTokensResp],
    responses=map_exceptions_to_responses(
        InvalidCredentialsException,
        EmployeeNotFoundByUsernameException,
    ),
)
async def login(
    body: CredsReq,
    auth_cookie_manager: AuthTokenManagerDep,
    ctx: Context,
) -> StdResponse[AuthTokensResp]:
    tokens = await ctx.auth_use_cases.login().execute(
        LoginDTO(
            username=body.username,
            password=body.password,
        ),
    )

    auth_cookie_manager.set_auth_cookies(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )

    return StdResponse(
        data=AuthTokensResp(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
        ),
    )


@auth_router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[AuthTokensResp],
    responses=map_exceptions_to_responses(
        InvalidCredentialsException,
        EmployeeNotFoundByUsernameException,
        UnauthorizedException,
        RefreshTokenNotFoundException,
    ),
)
async def refresh(
    body: RefreshTokenReq,
    auth_token_manager: AuthTokenManagerDep,
    ctx: Context,
) -> StdResponse[AuthTokensResp]:
    refresh_token = body.refresh_token

    if refresh_token is None:
        refresh_token = auth_token_manager.refresh_token_from_cookie

    if refresh_token is None:
        raise RefreshTokenNotFoundException

    tokens = await ctx.auth_use_cases.refresh().execute(
        RefreshDTO(
            refresh_token=refresh_token,
        ),
    )

    auth_token_manager.set_auth_cookies(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )

    return StdResponse(
        data=AuthTokensResp(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
        ),
    )
