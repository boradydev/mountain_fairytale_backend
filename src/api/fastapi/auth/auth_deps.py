from typing import Annotated

from fastapi import Depends, Request, Response

from src.infra.web.fastapi.cookies import AuthTokenManager
from src.api.fastapi.auth.abcs.tokens import IAuthTokenManager
from src.api.fastapi.common.deps import Context


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
