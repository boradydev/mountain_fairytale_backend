from fastapi.requests import Request

from src.infra.deps.app_ctx import AppContext


def get_app_ctx(request: Request) -> AppContext:
    return request.app.state.ctx
