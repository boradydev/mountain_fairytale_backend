from fastapi import APIRouter, status

from src.app.auth.usecases.login import LoginDTO
from src.app.auth.usecases.refresh import RefreshDTO
from src.domain.employees import employee_excs
from src.api.fastapi.auth.deps import AuthTokenManagerDep
from src.api.fastapi.auth.auth_excs import RefreshTokenNotFoundException
from src.api.fastapi.auth.auth_schemas import AuthTokensResp, CredsReq, RefreshTokenReq
from src.api.fastapi.common.deps import Context
from src.api.fastapi.common.handlers import map_exceptions_to_responses
from src.api.fastapi.common.schemas import StdResponse


auth_router = APIRouter(
    prefix="/auth",
    tags=["Авторизация"],
)


@auth_router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[AuthTokensResp],
    responses=map_exceptions_to_responses(
        employee_excs.InvalidCredentialsException,
        employee_excs.EmployeeNotFoundException,
        employee_excs.EmployeeDeactivateException,
    ),
    description="""
    Предусловие: Пользователь существует и активен.
    Действие: Аутентификация пользователя и выдача токенов.
    Результат:
        1. Возвращает токены в теле ответа.
        2. Устанавливает HTTP-only куки.
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
        employee_excs.EmployeeNotFoundException,
    ),
    description="""
        Предусловие: Сотрудник существует и активен.
        Действие: Обновление пары токенов доступа и обновления.
        Входные данные: refresh_token из тела запроса или из HTTP-only кук.
        Результат: 
            1. Возвращает новую пару токенов AuthTokensResp.
            2. Обновляет HTTP-only куки.
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
