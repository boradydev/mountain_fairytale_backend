import traceback
from collections.abc import Callable, Coroutine, Mapping
from logging import Logger
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from src.core.excs import BaseAppException
from src.common.api.exc_map import APP_EXCEPTION_MAP, Resp


def get_business_exception_handler(
    exception_map: Mapping[type[BaseAppException], Resp],
    logger: Logger,
) -> Callable[..., Coroutine[Any, Any, JSONResponse]]:
    async def handler(
        _: Request,
        exc: Exception,
    ) -> JSONResponse:
        if not isinstance(exc, BaseAppException):
            raise exc

        resp = exception_map.get(type(exc))

        if resp is None:
            logger.error(
                "Unmapped application exception: %s",
                type(exc).__name__,
                exc_info=exc,
            )

            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal Server Error",
                },
            )

        return JSONResponse(
            status_code=resp.status_code,
            content={
                "detail": resp.detail,
            },
        )

    return handler


def get_unknown_exception_handler(
    logger: Logger,
    debug: bool = False,
) -> Callable[..., Coroutine[Any, Any, JSONResponse]]:
    async def handler(
        _: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.error(
            exc,
            exc_info=True,
        )

        content = {
            "detail": "Internal Server Error",
        }

        if debug:
            content.update(
                {
                    "detail": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )

        return JSONResponse(
            status_code=500,
            content=content,
        )

    return handler


def map_exceptions_to_responses(
    *excs: type[BaseAppException],
    exception_map: Mapping[type[BaseAppException], Resp] = APP_EXCEPTION_MAP,
) -> dict[int | str, dict[str, Any]] | None:
    """
    Converts application exceptions into FastAPI router `responses` format.

    Extracts HTTP status codes and details from `exception_map` for given `excs`.
    Concatenates descriptions with ` | ` if multiple exceptions share the same status code.

    Args:
        *excs: Exception classes derived from `BaseAppException`.
        exception_map: Mapping of exceptions to their HTTP response models.

    Returns:
        Dict for FastAPI `@router.method(..., responses=...)` parameter.

    Example:
        `@router.post(..., responses=map_exceptions_to_responses(UserNotFound, BannedUser))`
    """
    responses: dict[int | str, dict[str, Any]] | None = {}

    for exc in excs:
        resp = exception_map.get(exc)

        if resp is None:
            responses.setdefault(
                500,
                {
                    "description": "Unmapped application exception",
                },
            )
            continue

        if resp.status_code not in responses:
            responses[resp.status_code] = {
                "description": resp.detail,
            }
        else:
            responses[resp.status_code]["description"] += f" | {resp.detail}"

    return responses
