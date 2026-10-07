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
from src.feat.sales_rep.api.sales_rep_schemas import (
    SalesRepresentativeResp,
    SalesRepresentativesResp,
    CreateSalesRepresentativeReq,
    UpdateSalesRepresentativeReq,
)
from src.feat.sales_rep.app.usecases.check_duplicate import CheckSalesRepresentativeDuplicateDTO
from src.feat.sales_rep.app.usecases.create import CreateSalesRepresentativeDTO
from src.feat.sales_rep.app.usecases.get import GetSalesRepresentativeDTO
from src.feat.sales_rep.app.usecases.get_all import GetSalesRepresentativesDTO
from src.feat.sales_rep.app.usecases.update import UpdateSalesRepresentativeDTO
from src.domain.sales_representatives import sales_representative_excs


"""
API CONTRACT — SALES REPRESENTATIVES

Этот модуль является источником требований к HTTP API торговых представителей.

Назначение:
    Управление данными торговых представителей.

Основные правила:
    1. Все эндпоинты защищены и доступны любому авторизованному пользователю.
    2. Торговый представитель не удаляется физически.
    3. Деактивация и повторная активация выполняются через PATCH с полем `isActive`.
    4. Создаваемые записи по умолчанию активны.
    5. ID торгового представителя является UUID.
    6. JSON использует camelCase через BaseSchema.
    7. Ответы обёрнуты в StdResponse.
    8. По умолчанию список содержит только активные записи; `includeDeactivated=true` включает всех.

Особенности данных:
    - name: 1–120 символов.
    - phone: 1–32 символа.
    - commission_percent: 0–100.
    - Поле phone уникально; попытка создания или обновления на существующий телефон вызывает 409 Conflict.

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


sales_representatives_router = APIRouter(
    prefix="/sales-representatives",
    tags=["Торговые представители"],
)


@sales_representatives_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[SalesRepresentativesResp],
    responses=map_exceptions_to_responses(UnauthorizedException),
    description="""
    Получение списка торговых представителей.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        Query parameter:
            include_deactivated: если true, вернуть всех торговых представителей, включая деактивированных (по умолчанию false).

    Результат:
        HTTP 200.
        data.sales_rep содержит список SalesRepresentativeResp.

    Критические сценарии для API-тестов:
        1. Получение списка только активных торговых представителей (include_deactivated=false).
        2. Получение списка всех торговых представителей (include_deactivated=true).
    """,
)
async def get_sales_representatives(
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
    include_deactivated: Annotated[bool, Query()] = False,
) -> StdResponse[SalesRepresentativesResp]:
    reps = await ctx.sales_representatives_use_cases.get_sales_representatives().execute(
        GetSalesRepresentativesDTO(include_deactivated=include_deactivated),
    )

    return StdResponse(
        data=SalesRepresentativesResp(
            sales_representatives=[SalesRepresentativeResp.model_validate(rep) for rep in reps],
        ),
    )


@sales_representatives_router.get(
    "/{sales_representative_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[SalesRepresentativeResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        sales_representative_excs.SalesRepresentativeNotFoundException,
    ),
    description="""
    Получение торгового представителя по UUID.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        sales_representative_id — UUID торгового представителя.

    Результат:
        HTTP 200.
        Возвращается полная сущность SalesRepresentativeResp независимо от её статуса активности.

    Ошибки:
        401 — пользователь не авторизован.
        404 — торговый представитель с указанным UUID не найден.

    Критические сценарии для API-тестов:
        1. Получение существующего активного торгового представителя.
        2. Получение существующего деактивированного торгового представителя.
        3. Получение несуществующего UUID -> 404.
    """,
)
async def get_sales_representative(
    sales_representative_id: UUID,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[SalesRepresentativeResp]:
    rep = await ctx.sales_representatives_use_cases.get_sales_representative().execute(
        GetSalesRepresentativeDTO(sales_representative_id=sales_representative_id),
    )

    return StdResponse(
        data=SalesRepresentativeResp.model_validate(rep),
    )


@sales_representatives_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=StdResponse[SalesRepresentativeResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        sales_representative_excs.SalesRepresentativePhoneAlreadyExistsException,
        sales_representative_excs.SalesRepresentativeDomainUpdateException,
    ),
    description="""
    Создание нового торгового представителя.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        CreateSalesRepresentativeReq:
            - name (1-120) — обязательное поле.
            - phone (1-32) — обязательное поле.
            - commission_percent (0-100) — обязательное поле.

    Результат:
        HTTP 201.
        data содержит созданного торгового представителя.
        Поля sales_representative_id, created_at, is_active (всегда true) назначаются сервером.

    Ошибки:
        401 — пользователь не авторизован.
        409 — торговый представитель с таким телефоном уже существует.
        422 — нарушение ограничений полей.

    Критические сценарии для API-тестов:
        1. Создание торгового представителя с валидными данными.
        2. Проверка, что созданная запись активна (isActive == true).
        3. Попытка создать торгового представителя с уже существующим телефоном -> 409.
        4. Проверка сохранения данных через GET по возвращенному sales_representative_id.
    """,
)
async def create_sales_representative(
    body: CreateSalesRepresentativeReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[SalesRepresentativeResp]:
    rep = await ctx.sales_representatives_use_cases.create_sales_representative().execute(
        CreateSalesRepresentativeDTO(
            actor_id=UUID(access_token_payload.employee_id),
            name=body.name,
            phone=body.phone,
            commission_percent=body.commission_percent,
        ),
    )

    return StdResponse(
        data=SalesRepresentativeResp.model_validate(rep),
    )


@sales_representatives_router.patch(
    "/{sales_representative_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[SalesRepresentativeResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        sales_representative_excs.SalesRepresentativeNotFoundException,
        sales_representative_excs.SalesRepresentativePhoneAlreadyExistsException,
        sales_representative_excs.SalesRepresentativeDomainUpdateException,
    ),
    description="""
    Обновление данных торгового представителя.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        Path: sales_representative_id — UUID торгового представителя.
        Body: UpdateSalesRepresentativeReq (поля: name, phone, commission_percent, is_active).

    Результат:
        HTTP 200.
        data содержит актуальное состояние торгового представителя.

    Ошибки:
        401 — пользователь не авторизован.
        404 — торговый представитель не найден.
        409 — новый телефон уже занят другим торговым представителем.
        422 — пустое тело запроса `{}` или нарушение доменных инвариантов.

    Важные требования:
        1. Деактивация/реактивация выполняется через поле is_active.
        2. Физического удаления нет.

    Критические сценарии для API-тестов:
        1. Изменение имени, телефона или процента комиссии.
        2. Деактивация активного торгового представителя (is_active: false).
        3. Реактивация деактивированного торгового представителя (is_active: true).
        4. Попытка изменить телефон на уже существующий -> 409.
        5. Пустой запрос -> 422.
        6. Проверка результата через GET.
    """,
)
async def update_sales_representative(
    sales_representative_id: UUID,
    body: UpdateSalesRepresentativeReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[SalesRepresentativeResp]:
    rep = await ctx.sales_representatives_use_cases.update_sales_representative().execute(
        UpdateSalesRepresentativeDTO(
            actor_id=UUID(access_token_payload.employee_id),
            sales_representative_id=sales_representative_id,
            payload=body.model_dump(exclude_unset=True),
        ),
    )

    return StdResponse(
        data=SalesRepresentativeResp.model_validate(rep),
    )


@sales_representatives_router.get(
    "/check-duplicate",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[SalesRepresentativeResp | NoneType],
    responses=map_exceptions_to_responses(UnauthorizedException),
    description="""
    Поиск дубликата торгового представителя.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        Query parameters: name (1-120), phone (1-32).

    Логика поиска:
        1. Требуются оба поля: name и phone.
        2. Кандидат подходит, только если:
           - similarity(name) >= 0.35 И
           - similarity(phone) >= 0.50.
        3. Совокупный score для ранжирования: (similarity(name) + similarity(phone)) / 2.
        4. Сортировка кандидатов:
           - По убыванию совокупного score.
           - При равенстве — по убыванию даты создания (created_at DESC).
           - При равенстве — по убыванию sales_representative_id DESC.
        5. Поиск осуществляется среди всех записей (и активных, и деактивированных).
        6. Из подходящих кандидатов выбирается один лучший.

    Результат:
        HTTP 200.
        data содержит SalesRepresentativeResp (лучший кандидат) или null, если совпадений не найдено.
        Поиск является справочным и не блокирует создание записей с похожими данными.

    Критические сценарии для API-тестов:
        1. Поиск по обоим полям с точным совпадением -> возвращается торговый представитель.
        2. Поиск, где name_similarity >= 0.35 и phone_similarity >= 0.50 -> возвращается торговый представитель.
        3. Поиск, где name_similarity < 0.35 (даже если phone совпадает точно) -> data == null.
        4. Поиск, где phone_similarity < 0.50 (даже если name совпадает точно) -> data == null.
        5. Поиск деактивированного торгового представителя -> возвращается торговый представитель.
        6. При нескольких кандидатах с одинаковым совокупным score возвращается самый новый.
    """,
)
async def check_duplicate_sales_representative(
    name: Annotated[str, Query(min_length=1, max_length=120)],
    phone: Annotated[str, Query(min_length=1, max_length=32)],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[SalesRepresentativeResp | None]:
    rep = await ctx.sales_representatives_use_cases.check_duplicate().execute(
        CheckSalesRepresentativeDuplicateDTO(name=name, phone=phone),
    )

    return StdResponse(
        data=(SalesRepresentativeResp.model_validate(rep) if rep is not None else None),
    )
