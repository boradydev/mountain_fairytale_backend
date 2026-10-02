import traceback
from collections.abc import Callable, Coroutine, Mapping
from logging import Logger
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.core.excs import BaseAppException
from src.presentation.fastapi.common.types import Resp


def get_business_exception_handler(
    exception_map: Mapping[type[BaseAppException], Resp],
) -> Callable[..., Coroutine[Any, Any, JSONResponse]]:
    """
    Создает универсальный асинхронный обработчик для исключений приложения.

    Функция трансформирует внутренние исключения (BaseAppException) в HTTP-ответы
    на основе предоставленной карты (exception_map).

    Логика обработки:
        1. Если тип исключения найден в exception_map, возвращается JSONResponse
           с соответствующим статусом и деталями.
        2. Если маппинг для данного исключения отсутствует, оно пробрасывается
           дальше (raise), позволяя глобальному обработчику (unknown_exception_handler)
           зафиксировать ошибку с полным Traceback для дебага.

    Args:
        exception_map: Словарь, сопоставляющий классы исключений их
            HTTP-представлениям (Resp).

    Returns:
        Callable: Асинхронная функция-обработчик, совместимая с интерфейсом FastAPI.

    Raises:
        Exception: Если переданный объект не является ошибкой валидации.
    """

    async def handler(_: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, BaseAppException):
            resp = exception_map.get(type(exc))
            if resp:
                return JSONResponse(
                    status_code=resp.status_code,
                    content={
                        "detail": resp.detail,
                    },
                )

        raise exc

    return handler


async def validation_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """
    Обработчик исключений валидации Pydantic (RequestValidationError).

    Трансформирует системную ошибку валидации FastAPI/Pydantic в унифицированный
    формат ответа приложения (422 Unprocessable Entity).

    Логика обработки:
        1. Если исключение является RequestValidationError, возвращается
           JSONResponse с детальным описанием ошибок валидации.
        2. В случае несоответствия типа (защитная проверка), исключение
           пробрасывается выше (raise) в глобальный обработчик для
           фиксации непредвиденной ошибки в логах.

    Args:
        _: Объект запроса (требуется сигнатурой FastAPI).
        exc: Выброшенное исключение.

    Returns:
        JSONResponse: Ответ со статусом 422 и деталями валидации.

    Raises:
        Exception: Если переданный объект не является ошибкой валидации.
    """
    if isinstance(exc, RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "detail": str(exc.errors()),
            },
        )

    raise exc


def get_unknown_exception_handler(
    logger: Logger,
    debug: bool = False,
) -> Callable[..., Coroutine[Any, Any, JSONResponse]]:
    """Создает обработчик непредвиденных системных исключений."""

    async def handler(
        _: Request,
        exc: Exception,
    ) -> JSONResponse:
        """
        Обработчик.

        Хендлер перехватывает любые необработанные ошибки (KeyError, ValueError и др.),
        предотвращая падение процесса и обеспечивая унифицированный ответ клиенту.

        Логика работы:
        1. Логирование: Ошибка записывается через `Logger` с `exc_info=True`,
           что сохраняет полный traceback в логах для последующего анализа.
        2. Безопасность: В режиме `debug=False` пользователю отдается только
           общий текст "Internal Server Error".
        3. Отладка: В режиме `debug=True` в ответ включается описание ошибки
           и строковый traceback для быстрой диагностики без проверки логов.

        Args:
        _: Request: Объект запроса (не используется).
        exc: Exception: Возникшее исключение.

        Returns:
        JSONResponse: Ответ со статусом 500 и деталями в зависимости от режима debug.
        """
        logger.error(exc, exc_info=True)
        content = {"detail": "Internal Server Error"}
        if debug:
            content.update(
                {
                    "detail": str(exc),
                    "traceback": traceback.format_exc(),
                }
            )

        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal Server Error",
            },
        )

    return handler
