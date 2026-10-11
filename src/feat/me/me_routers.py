from types import NoneType
from uuid import UUID

from fastapi import APIRouter, Request, Response, status

from src.common.api.api_excs import UnauthorizedException
from src.common.api.deps import (
    AccessTokenPayloadDep,
    Context,
)
from src.common.api.excs_handlers import map_exceptions_to_responses
from src.common.api.schemas import StdResponse
from src.common.infra.services.token.excs import InvalidAccessTokenException
from src.common.infra.services.token.settings import JwtSettings
from src.common.infra.web.fastapi.auth_token_manager import AuthTokenManager
from src.feat.employees.api.employee_schemas import ChangeEmployeePasswordReq
from src.feat.employees.app.usecases.change_password import (
    ChangeEmployeePasswordDTO,
)
from src.feat.employees.app.usecases.get import GetEmployeeDTO
from src.feat.employees.domain.employee_excs import EmployeeNotFoundException
from src.feat.me.me_schemas import CurrentEmployeeResp


"""
API CONTRACT — CURRENT USER

Этот модуль является источником требований к API текущего авторизованного
пользователя.

Назначение:
    Операции, которые выполняются непосредственно над текущей учётной записью.

Основные правила:
    1. Идентификатор текущего пользователя берётся из access token.
    2. Клиент не передаёт employee_id для операций над собственной учётной записью.
    3. Logout удаляет app cookies.
    4. Смена собственного пароля не должна требовать передачи employee_id.
    5. Пароль никогда не возвращается API.

Авторизация:
    Токен доступа (access token) может быть передан двумя способами:
    1. Через Cookies: кука `access-token`.
    2. Через Headers (для Flutter): заголовок `Authorization: Bearer <token>`.

AI TESTING RULES:

    1. Тестировать только HTTP API.
    2. Не использовать use cases для определения ожидаемого поведения.
    3. Ожидаемое поведение определять только из:
        - router;
        - schemas;
        - exceptions;
        - APP_EXCEPTION_MAP;
        - exception handlers.
    4. Use cases и нижние уровни могут содержать ошибки.
       API-тесты должны быть способны их обнаруживать.
    5. Для проверки текущего пользователя использовать реальные access tokens.
    6. Проверять не только HTTP status code, но и фактическое состояние cookies
       и данных пользователя.
"""


me_router = APIRouter(
    prefix="/me",
    tags=["Текущий пользователь"],
)


@me_router.get(
    "",
    response_model=StdResponse[CurrentEmployeeResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        InvalidAccessTokenException,
        EmployeeNotFoundException,
    ),
    description="Текущий сотрудник из проверенного access token. "
    "Возвращает актуальные employeeId, username, role. "
    "Деактивация не отзывает действующий access token.",
)
async def get_me(
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[CurrentEmployeeResp]:
    employee = await ctx.employees_use_cases.get_employee().execute(
        GetEmployeeDTO(employee_id=UUID(access_token_payload.employee_id)),
    )
    return StdResponse(data=CurrentEmployeeResp.model_validate(employee))


@me_router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        InvalidAccessTokenException,
    ),
    description="""
    Выход текущего пользователя из системы.

    Предусловие:
        Должен быть передан валидный access token.

    Действие:
        Удалить authentication cookies текущего клиента.

    Результат:
        HTTP 200.
        message:
            "Выход выполнен."

    Важные требования:
        1. Auth cookies должны быть удалены.
        2. Endpoint не должен изменять данные сотрудника.
        3. Logout относится к текущей сессии/клиенту.

    Ошибки:
        401 — access token отсутствует или авторизация не выполнена.

    Критические сценарии для API-тестов:
        1. Logout авторизованного пользователя.
        2. Проверка HTTP 200.
        3. Проверка удаления app cookies.
        4. Logout без access token -> 401.
    """,
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
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        InvalidAccessTokenException,
        EmployeeNotFoundException,
    ),
    description="""
    Изменение пароля текущего пользователя.

    Предусловие:
        Пользователь авторизован.

    Входные данные:
        Body:
            ChangeEmployeePasswordReq:
                password — новый пароль.

    Важное правило:
        employee_id не передаётся клиентом.
        Идентификатор текущего пользователя определяется из access token.

    Результат:
        HTTP 200.
        message:
            "Пароль изменён."

    Ошибки:
        401 — пользователь не авторизован.
        404 — пользователь из access token не найден.

    Критические сценарии для API-тестов:
        1. Авторизованный пользователь меняет собственный пароль.
        2. Проверка HTTP 200.
        3. Проверка message.
        4. Попытка выполнить операцию без access token -> 401.
        5. Проверка, что изменить пароль можно только текущему пользователю.
        6. Проверка, что employee_id из запроса не используется для выбора
           пользователя.
    """,
)
async def change_password(
    body: ChangeEmployeePasswordReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[NoneType]:
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
