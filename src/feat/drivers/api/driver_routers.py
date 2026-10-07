from types import NoneType
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from src.common.api.api_excs import UnauthorizedException
from src.common.api.deps import (
    AccessTokenPayloadDep,
    Context,
)
from src.common.api.excs_handlers import map_exceptions_to_responses
from src.common.api.schemas import StdResponse
from src.feat.drivers.api.driver_schemas import (
    DriverResp,
    DriversResp,
    CreateDriverReq,
    UpdateDriverReq,
)
from src.feat.drivers.app.usecases.check_duplicate import CheckDriverDuplicateDTO
from src.feat.drivers.app.usecases.create import CreateDriverDTO
from src.feat.drivers.app.usecases.get import GetDriverDTO
from src.feat.drivers.app.usecases.get_all import GetDriversDTO
from src.feat.drivers.app.usecases.update import UpdateDriverDTO
from src.feat.drivers.domain import driver_excs

"""
API CONTRACT — DRIVERS

Этот модуль является источником требований к HTTP API водителей.

Назначение:
    Управление данными водителей.

Основные правила:
    1. Все эндпоинты защищены и доступны любому авторизованному пользователю.
    2. Водитель не удаляется физически.
    3. Деактивация и повторная активация выполняются через PATCH с полем `isActive`.
    4. Создаваемые записи по умолчанию активны.
    5. ID водителя является UUID.
    6. JSON использует camelCase через BaseSchema.
    7. Ответы обёрнуты в StdResponse.
    8. По умолчанию список содержит только активные записи; `includeDeactivated=true` включает всех.

Особенности данных:
    - name: 1–120 символов.
    - Уникальность имени (name) НЕ обеспечивается ни на уровне домена, ни на уровне БД.
    - Совпадающие или похожие ФИО допустимы.

Авторизация:
    Токен доступа (access token) может быть передан двумя способами:
    1. Через Cookies: кука `access-token`.
    2. Через Headers (для Flutter): заголовок `Authorization: Bearer <token>`.

AI TESTING RULES:
    1. Тестировать HTTP API через публичные endpoints этого router.
    2. Не использовать use cases для определения ожидаемого поведения API.
    3. Не анализировать repositories/services для определения требований.
    4. Ожидаемое поведение определять только из: router, schemas, domain/API exceptions.
    5. Изменение состояния выполнять через реальные HTTP-запросы API.
    6. Проверять HTTP status code и тело ответа.
    7. Проверять фактическое изменение состояния после POST/PUT/PATCH через GET.
    8. Проверять, что деактивированные записи и их данные сохраняются.
    9. Не использовать реализацию use case/repository как источник ожидаемого поведения.
"""


drivers_router = APIRouter(
    prefix="/app",
    tags=["Водители"],
)


@drivers_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DriversResp],
    responses=map_exceptions_to_responses(UnauthorizedException),
    description="""
    Получение списка водителей.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        Query parameter:
            include_deactivated: если true, вернуть всех водителей, включая деактивированных (по умолчанию false).

    Результат:
        HTTP 200.
        data.app содержит список DriverResp.

    Критические сценарии для API-тестов:
        1. Получение списка только активных водителей (include_deactivated=false).
        2. Получение списка всех водителей (include_deactivated=true).
    """,
)
async def get_drivers(
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
    include_deactivated: Annotated[bool, Query()] = False,
) -> StdResponse[DriversResp]:
    drivers = await ctx.drivers_use_cases.get_drivers().execute(
        GetDriversDTO(include_deactivated=include_deactivated),
    )

    return StdResponse(
        data=DriversResp(
            drivers=[DriverResp.model_validate(driver) for driver in drivers],
        ),
    )


@drivers_router.get(
    "/{driver_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DriverResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        driver_excs.DriverNotFoundException,
    ),
    description="""
    Получение водителя по UUID.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        driver_id — UUID водителя.

    Результат:
        HTTP 200.
        Возвращается полная сущность DriverResp независимо от её статуса активности.

    Ошибки:
        401 — пользователь не авторизован.
        404 — водитель с указанным UUID не найден.

    Критические сценарии для API-тестов:
        1. Получение существующего активного водителя.
        2. Получение существующего деактивированного водителя.
        3. Получение несуществующего UUID -> 404.
    """,
)
async def get_driver(
    driver_id: UUID,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DriverResp]:
    driver = await ctx.drivers_use_cases.get_driver().execute(
        GetDriverDTO(driver_id=driver_id),
    )

    return StdResponse(
        data=DriverResp.model_validate(driver),
    )


@drivers_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=StdResponse[DriverResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        driver_excs.DriverDomainUpdateException,
    ),
    description="""
    Создание нового водителя.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        CreateDriverReq:
            - name (1-120) — обязательное поле.

    Результат:
        HTTP 201.
        data содержит созданного водителя.
        Поля driver_id, created_at, is_active (всегда true) назначаются сервером.

    Важные требования:
        1. Создание водителя НЕ блокируется при наличии дубликатов или похожих имен.
        2. Результат `/check-duplicate` не проверяется в процессе создания.

    Ошибки:
        401 — пользователь не авторизован.
        422 — нарушение ограничений полей.

    Критические сценарии для API-тестов:
        1. Создание водителя с валидным именем.
        2. Создание водителя с именем, которое уже существует в системе (должно пройти успешно).
        3. Проверка, что созданный водитель активен (isActive == true).
        4. Проверка сохранения данных через GET по возвращенному driver_id.
    """,
)
async def create_driver(
    body: CreateDriverReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DriverResp]:
    driver = await ctx.drivers_use_cases.create_driver().execute(
        CreateDriverDTO(
            actor_id=UUID(access_token_payload.employee_id),
            name=body.name,
        ),
    )

    return StdResponse(
        data=DriverResp.model_validate(driver),
    )


@drivers_router.patch(
    "/{driver_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DriverResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        driver_excs.DriverNotFoundException,
        driver_excs.DriverDomainUpdateException,
    ),
    description="""
    Обновление данных водителя.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        Path: driver_id — UUID водителя.
        Body: UpdateDriverReq (поля: name, is_active).

    Результат:
        HTTP 200.
        data содержит актуальное состояние водителя.

    Ошибки:
        401 — пользователь не авторизован.
        404 — водитель не найден.
        422 — пустое тело запроса `{}` или нарушение доменных инвариантов.

    Важные требования:
        1. Деактивация/реактивация выполняется через поле is_active.
        2. Физического удаления нет.

    Критические сценарии для API-тестов:
        1. Изменение имени водителя.
        2. Деактивация активного водителя (is_active: false).
        3. Реактивация деактивированного водителя (is_active: true).
        4. Пустой запрос -> 422.
        5. Проверка результата через GET.
    """,
)
async def update_driver(
    driver_id: UUID,
    body: UpdateDriverReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DriverResp]:
    driver = await ctx.drivers_use_cases.update_driver().execute(
        UpdateDriverDTO(
            actor_id=UUID(access_token_payload.employee_id),
            driver_id=driver_id,
            payload=body.model_dump(exclude_unset=True),
        ),
    )

    return StdResponse(
        data=DriverResp.model_validate(driver),
    )


@drivers_router.get(
    "/check-duplicate",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DriverResp | NoneType],
    responses=map_exceptions_to_responses(UnauthorizedException),
    description="""
    Поиск дубликата водителя.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        Query parameter: name (1-120).

    Логика поиска:
        1. Порог similarity: name >= 0.35.
        2. Поиск осуществляется среди всех записей (и активных, и деактивированных).
        3. Выбор лучшего кандидата:
            - Сначала по убыванию similarity score.
            - При равном score — по убыванию даты создания (created_at DESC).
            - При равной дате — по убыванию driver_id DESC.

    Результат:
        HTTP 200.
        data содержит DriverResp (лучший кандидат) или null, если совпадений не найдено.

    Критические сценарии для API-тестов:
        1. Поиск по имени с точным совпадением -> возвращается водитель.
        2. Поиск по имени с частичным совпадением выше порога (0.35) -> возвращается водитель.
        3. Поиск по имени, не достигающему порога -> data == null.
        4. Поиск деактивированного водителя -> возвращается водитель.
        5. При нескольких кандидатах с одинаковым similarity возвращается самый новый.
    """,
)
async def check_duplicate_driver(
    name: Annotated[str, Query(min_length=1, max_length=120)],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DriverResp | None]:
    driver = await ctx.drivers_use_cases.check_duplicate().execute(
        CheckDriverDuplicateDTO(name=name),
    )

    return StdResponse(
        data=(DriverResp.model_validate(driver) if driver is not None else None),
    )
