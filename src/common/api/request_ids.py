from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from src.core.request_id import request_id


def install_request_ids(app: FastAPI) -> None:
    @app.middleware("http")
    async def identify(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        identifier = uuid4().hex
        request.state.request_id = identifier
        token = request_id.set(identifier)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = identifier
            return response
        finally:
            request_id.reset(token)
