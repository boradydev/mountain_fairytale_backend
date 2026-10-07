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
from src.feat.products.api.product_schemas import (
    ProductResp,
    ProductsResp,
    CreateProductReq,
    UpdateProductReq,
)
from src.feat.products.app.usecases.check_duplicate import CheckProductDuplicateDTO
from src.feat.products.app.usecases.create import CreateProductDTO
from src.feat.products.app.usecases.get import GetProductDTO
from src.feat.products.app.usecases.get_all import GetProductsDTO
from src.feat.products.app.usecases.update import UpdateProductDTO
from src.feat.products.domain import product_excs

"""
API CONTRACT — PRODUCTS

Этот модуль является источником требований к HTTP API товаров.

Назначение:
    Управление каталогом товаров.

Основные правила:
    1. Все эндпоинты защищены и доступны любому авторизованному пользователю.
    2. Товар не удаляется физически.
    3. Деактивация и повторная активация выполняются через PATCH с полем `isActive`.
    4. Создаваемые записи по умолчанию активны.
    5. ID товара является UUID.
    6. JSON использует camelCase через BaseSchema.
    7. Ответы обёрнуты в StdResponse.
    8. По умолчанию список содержит только активные записи; `includeDeactivated=true` включает всех.

Особенности данных:
    - name: 1–120 символов.
    - base_price: 0–1 000 000 000.
    - Поле name уникально: проверка выполняется по точному совпадению, регистрозависимо, 
      без обрезки пробелов и нормализации. "Product" и "product" — разные имена.
      Похожее, но не идентичное имя допустимо. Попытка создания или обновления на 
      точно такое же имя вызывает 409 Conflict.

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


products_router = APIRouter(
    prefix="/app",
    tags=["Товары"],
)


@products_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[ProductsResp],
    responses=map_exceptions_to_responses(UnauthorizedException),
    description="""
    Получение списка товаров.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        Query parameter:
            include_deactivated: если true, вернуть все товары, включая деактивированные (по умолчанию false).

    Результат:
        HTTP 200.
        data.app содержит список ProductResp.

    Критические сценарии для API-тестов:
        1. Получение списка только активных товаров (include_deactivated=false).
        2. Получение списка всех товаров (include_deactivated=true).
    """,
)
async def get_products(
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
    include_deactivated: Annotated[bool, Query()] = False,
) -> StdResponse[ProductsResp]:
    products = await ctx.products_use_cases.get_products().execute(
        GetProductsDTO(include_deactivated=include_deactivated),
    )

    return StdResponse(
        data=ProductsResp(
            products=[ProductResp.model_validate(p) for p in products],
        ),
    )


@products_router.get(
    "/{product_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[ProductResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        product_excs.ProductNotFoundException,
    ),
    description="""
    Получение товара по UUID.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        product_id — UUID товара.

    Результат:
        HTTP 200.
        Возвращается полная сущность ProductResp независимо от её статуса активности.

    Ошибки:
        401 — пользователь не авторизован.
        404 — товар с указанным UUID не найден.

    Критические сценарии для API-тестов:
        1. Получение существующего активного товара.
        2. Получение существующего деактивированного товара.
        3. Получение несуществующего UUID -> 404.
    """,
)
async def get_product(
    product_id: UUID,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[ProductResp]:
    product = await ctx.products_use_cases.get_product().execute(
        GetProductDTO(product_id=product_id),
    )

    return StdResponse(
        data=ProductResp.model_validate(product),
    )


@products_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=StdResponse[ProductResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        product_excs.ProductNameAlreadyExistsException,
    ),
    description="""
    Создание нового товара.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        CreateProductReq:
            - name (1-120) — обязательное поле.
            - base_price (0-1 000 000 000) — обязательное поле.

    Результат:
        HTTP 201.
        data содержит созданный товар.
        Поля product_id, created_at, is_active (всегда true) назначаются сервером.

    Ошибки:
        401 — пользователь не авторизован.
        409 — товар с таким именем уже существует.
        422 — нарушение ограничений полей.

    Критические сценарии для API-тестов:
        1. Создание товара с валидными данными.
        2. Проверка, что созданный товар активен (isActive == true).
        3. Попытка создать товар с уже существующим именем -> 409.
        4. Проверка сохранения данных через GET по возвращенному product_id.
    """,
)
async def create_product(
    body: CreateProductReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[ProductResp]:
    product = await ctx.products_use_cases.create_product().execute(
        CreateProductDTO(
            actor_id=UUID(access_token_payload.employee_id),
            name=body.name,
            base_price=body.base_price,
        ),
    )

    return StdResponse(
        data=ProductResp.model_validate(product),
    )


@products_router.patch(
    "/{product_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[ProductResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        product_excs.ProductNotFoundException,
        product_excs.ProductNameAlreadyExistsException,
        product_excs.ProductDomainUpdateException,
    ),
    description="""
    Обновление данных товара.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        Path: product_id — UUID товара.
        Body: UpdateProductReq (поля: name, base_price, is_active).

    Результат:
        HTTP 200.
        data содержит актуальное состояние товара.

    Ошибки:
        401 — пользователь не авторизован.
        404 — товар не найден.
        409 — новое имя уже занято другим товаром.
        422 — пустое тело запроса `{}` или нарушение доменных инвариантов.

    Важные требования:
        1. Деактивация/реактивация выполняется через поле is_active.
        2. Физического удаления нет.

    Критические сценарии для API-тестов:
        1. Изменение имени или цены товара.
        2. Деактивация активного товара (is_active: false).
        3. Реактивация деактивированного товара (is_active: true).
        4. Попытка изменить имя на уже существующее -> 409.
        5. Пустой запрос -> 422.
        6. Проверка результата через GET.
    """,
)
async def update_product(
    product_id: UUID,
    body: UpdateProductReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[ProductResp]:
    product = await ctx.products_use_cases.update_product().execute(
        UpdateProductDTO(
            actor_id=UUID(access_token_payload.employee_id),
            product_id=product_id,
            payload=body.model_dump(exclude_unset=True),
        ),
    )

    return StdResponse(
        data=ProductResp.model_validate(product),
    )


@products_router.get(
    "/check-duplicate",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[ProductResp | NoneType],
    responses=map_exceptions_to_responses(UnauthorizedException),
    description="""
    Поиск дубликата товара.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        Query parameter: name (1-120).

    Логика поиска:
        1. Порог similarity: name >= 0.35 (включительно).
        2. Поиск осуществляется среди всех записей (и активных, и деактивированных).
        3. Выбор лучшего кандидата:
            - Сначала по убыванию similarity score (DESC).
            - При равном score — по убыванию даты создания (created_at DESC).
            - При равной дате — по убыванию product_id (DESC).

    Результат:
        HTTP 200.
        data содержит ProductResp (лучший кандидат) или null, если совпадений не найдено.
        Проверка является справочной и не блокирует создание товара с похожим именем.

    Критические сценарии для API-тестов:
        1. Поиск по имени с точным совпадением -> возвращается товар.
        2. Поиск по имени с частичным совпадением выше порога (0.35) -> возвращается товар.
        3. Поиск по имени, не достигающему порога -> data == null.
        4. Поиск деактивированного товара -> возвращается товар.
    """,
)
async def check_duplicate_product(
    name: Annotated[str, Query(min_length=1, max_length=120)],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[ProductResp | None]:
    product = await ctx.products_use_cases.check_duplicate().execute(
        CheckProductDuplicateDTO(name=name),
    )

    return StdResponse(
        data=(ProductResp.model_validate(product) if product is not None else None),
    )
