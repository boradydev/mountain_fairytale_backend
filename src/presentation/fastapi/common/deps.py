from typing import Annotated

from fastapi import Depends
from fastapi.requests import Request

from src.infra.factories.app_context import AppContext
from src.presentation.fastapi.common.excs import UnauthorizedHTTPException
from src.presentation.fastapi.employees.schemas import AccessTokenPyload


def get_app_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


Context = Annotated[AppContext, Depends(get_app_ctx)]


def get_access_token_pyload(
    request: Request,
    ctx: Context,
) -> AccessTokenPyload:
    access_token = request.headers.get("access_token")
    if access_token is None:
        raise UnauthorizedHTTPException

    return ctx.token_service.get_payload_access_token(access_token=access_token)

AccessTokenPayloadDep = Annotated[AccessTokenPyload, Depends(get_access_token_pyload)]
