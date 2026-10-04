from fastapi import APIRouter, status

from src.api.fastapi.common.deps import AuthTokenManagerDep
from src.api.fastapi.auth.auth_schemas import AuthTokensResp, CredsReq, RefreshTokenReq
from src.api.fastapi.common.api_excs import RefreshTokenNotFoundException
from src.api.fastapi.common.deps import Context
from src.api.fastapi.common.excs_handlers import map_exceptions_to_responses
from src.api.fastapi.common.schemas import StdResponse
from src.app.auth.usecases.login import LoginDTO
from src.app.auth.usecases.refresh import RefreshDTO
from src.domain.auth import auth_excs


"""
API CONTRACT — AUTHENTICATION

Этот модуль является источником требований к HTTP API авторизации.

Назначение:
    Предоставление публичных endpoints для входа пользователя в систему
    и обновления пары JWT-токенов.

Endpoints:
    POST /public/auth/login
    POST /public/auth/refresh

Основные правила безопасности:

    1. Авторизация выполняется по username и password.
    2. При успешной авторизации выдаются access и refresh tokens.
    3. Access token используется для доступа к защищённым endpoints.
    4. Refresh token используется для получения новой пары токенов.
    5. Refresh token может передаваться в теле запроса или через cookie,
       в зависимости от предусмотренного endpoint поведения.
    6. При успешной авторизации и обновлении токенов auth cookies
       устанавливаются или обновляются.
    7. Необходимо исключить User Enumeration:
       API не должен раскрывать, существует ли пользователь с указанным
       username.
    8. Деактивированный сотрудник не может авторизоваться или обновить токены.
    9. Пароль никогда не возвращается API.
    10. JWT-токены не должны содержать пароль или password hash.

AI TESTING RULES:

    1. Тестировать HTTP API через публичные endpoints.
    2. Не использовать use cases для определения ожидаемого поведения.
    3. Не анализировать repositories/services для определения требований.
    4. Ожидаемое поведение определять только из:
        - router;
        - schemas;
        - domain/API exceptions;
        - APP_EXCEPTION_MAP;
        - exception handlers.
    5. Реализация use cases, repositories и services может содержать ошибки.
       API-тесты должны быть способны обнаруживать эти ошибки.
    6. Использовать реальную тестовую PostgreSQL.
    7. Использовать реальные JWT-токены, созданные тестовой конфигурацией.
    8. Не подменять успешные JWT-токены произвольными строками.
    9. Проверять не только status code, но и содержимое ответа.
    10. Проверять cookies отдельно от JSON response.
    11. Проверять, что после refresh старые и новые токены обрабатываются
        согласно контракту endpoint.
    12. Проверять, что деактивированный сотрудник не может получить
        новую пару токенов.
    13. Проверять, что ошибки авторизации не раскрывают существование
        username.
"""

auth_router = APIRouter(
    prefix="/auth",
    tags=["Авторизация"],
)


@auth_router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[AuthTokensResp],
    responses=map_exceptions_to_responses(
        auth_excs.InvalidCredentialsException,
        auth_excs.AuthEmployeeNotFoundByUsernameException,
        auth_excs.AuthEmployeeDeactivateException,
    ),
    description="""
    Предусловие: Пользователь существует и активен.
    Действие: Аутентификация пользователя и выдача токенов.
    Результат:
        1. Body (camelCase): токены для windows клиентов (Flutter).
        2. Cookies (kebab-case): Для веб-клиентов (Browser).
    Критические сценарии:
        1. Неверные логин или пароль.
        2. Сотрудник не существует.
        3. Сотрудник деактивирован.
    """,
)
async def login(
    body: CredsReq,
    auth_token_manager: AuthTokenManagerDep,
    ctx: Context,
) -> StdResponse[AuthTokensResp]:
    tokens = await ctx.auth_use_cases.login().execute(
        LoginDTO(
            username=body.username,
            password=body.password,
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


@auth_router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[AuthTokensResp],
    responses=map_exceptions_to_responses(
        RefreshTokenNotFoundException,
        auth_excs.AuthEmployeeNotFoundException,
        auth_excs.AuthEmployeeDeactivateException,
    ),
    description="""
        Предусловие: Сотрудник существует и активен.
        Действие: Обновление пары токенов доступа и обновления.
        Входные данные: refresh_token из тела запроса или из HTTP-only кук.
        Результат:
            1. Body (camelCase): токены для windows клиентов (Flutter).
            2. Cookies (kebab-case): Для веб-клиентов (Browser).
        Критические сценарии:
            1. Не передан токен обновления.
            2. Сотрудник не существует.
            3. Сотрудник деактивирован.
    """,
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
