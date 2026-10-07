from typing import Annotated

from fastapi import Depends, Request, Response

from src.feat.auth.api.abcs.auth_token_manager_abcs import IAuthTokenManager
from src.feat.auth.api.auth_schemas import AccessTokenPyload
from src.api.fastapi.common.api_excs import UnauthorizedException, ForbiddenException
from src.infra.factories.app_context import AppContext
from src.infra.web.fastapi.auth_token_manager import AuthTokenManager


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


def verify_admin_access(
    access_token_payload: AccessTokenPayloadDep,
) -> None:
    if access_token_payload.role != "admin":
        raise ForbiddenException
