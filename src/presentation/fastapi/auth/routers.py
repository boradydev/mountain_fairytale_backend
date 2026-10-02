from fastapi import APIRouter, status

from src.app.auth.usecases.login import LoginDTO
from src.app.auth.usecases.refresh import RefreshDTO
from src.presentation.fastapi.auth import responses
from src.presentation.fastapi.auth.deps import AuthTokenManagerDep
from src.presentation.fastapi.auth.excs import UnauthorizedException
from src.presentation.fastapi.common.deps import Context
from src.presentation.fastapi.common.schemas import StdResponse
from src.presentation.fastapi.auth.schemas import CredsReq, RefreshTokenReq, AuthTokensResp

auth_router = APIRouter(
    prefix="/auth",
    tags=["Авторизация"],
)


@auth_router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[AuthTokensResp],
    responses=responses.LOGIN
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
    responses=responses.REFRESH
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
        raise UnauthorizedException

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
