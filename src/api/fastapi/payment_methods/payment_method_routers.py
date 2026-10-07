from types import NoneType
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from src.api.fastapi.common.api_excs import UnauthorizedException
from src.api.fastapi.common.deps import (
    AccessTokenPayloadDep,
    Context,
)
from src.api.fastapi.common.excs_handlers import map_exceptions_to_responses
from src.api.fastapi.common.schemas import StdResponse
from src.api.fastapi.payment_methods.payment_method_schemas import (
    PaymentMethodResp,
    PaymentMethodsResp,
    CreatePaymentMethodReq,
    UpdatePaymentMethodReq,
)
from src.app.payment_methods.usecases.check_duplicate import CheckPaymentMethodDuplicateDTO
from src.app.payment_methods.usecases.create import CreatePaymentMethodDTO
from src.app.payment_methods.usecases.get import GetPaymentMethodDTO
from src.app.payment_methods.usecases.get_all import GetPaymentMethodsDTO
from src.app.payment_methods.usecases.update import UpdatePaymentMethodDTO
from src.domain.payment_methods import payment_method_excs


"""
API CONTRACT — PAYMENT METHODS

Этот модуль является источником требований к HTTP API способов оплаты.

Назначение:
    Управление способами оплаты.

Основные правила:
    1. Все эндпоинты защищены и доступны любому авторизованному пользователю.
    2. Способ оплаты не удаляется физически.
    3. Деактивация и повторная активация выполняются через PATCH с полем `isActive`.
    4. Создаваемые записи по умолчанию активны.
    5. ID способа оплаты является UUID.
    6. JSON использует camelCase через BaseSchema.
    7. Ответы обёрнуты в StdResponse.
    8. По умолчанию список содержит только активные записи; `includeDeactivated=true` включает всех.

Особенности данных:
    - name: 1–120 символов.
    - Поле name уникально; попытка создания или обновления на существующее имя вызывает 409 Conflict.

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


payment_methods_router = APIRouter(
    prefix="/payment-methods",
    tags=["Способы оплаты"],
)


@payment_methods_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[PaymentMethodsResp],
    responses=map_exceptions_to_responses(UnauthorizedException),
    description="""
    Получение списка способов оплаты.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        Query parameter:
            include_deactivated: если true, вернуть все способы оплаты, включая деактивированные (по умолчанию false).

    Результат:
        HTTP 200.
        data.payment_methods содержит список PaymentMethodResp.

    Критические сценарии для API-тестов:
        1. Получение списка только активных способов оплаты (include_deactivated=false).
        2. Получение списка всех способов оплаты (include_deactivated=true).
    """,
)
async def get_payment_methods(
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
    include_deactivated: Annotated[bool, Query()] = False,
) -> StdResponse[PaymentMethodsResp]:
    payment_methods = await ctx.payment_methods_use_cases.get_payment_methods().execute(
        GetPaymentMethodsDTO(include_deactivated=include_deactivated),
    )

    return StdResponse(
        data=PaymentMethodsResp(
            payment_methods=[PaymentMethodResp.model_validate(pm) for pm in payment_methods],
        ),
    )


@payment_methods_router.get(
    "/{payment_method_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[PaymentMethodResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        payment_method_excs.PaymentMethodNotFoundException,
    ),
    description="""
    Получение способа оплаты по UUID.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        payment_method_id — UUID способа оплаты.

    Результат:
        HTTP 200.
        Возвращается полная сущность PaymentMethodResp независимо от её статуса активности.

    Ошибки:
        401 — пользователь не авторизован.
        404 — способ оплаты с указанным UUID не найден.

    Критические сценарии для API-тестов:
        1. Получение существующего активного способа оплаты.
        2. Получение существующего деактивированного способа оплаты.
        3. Получение несуществующего UUID -> 404.
    """,
)
async def get_payment_method(
    payment_method_id: UUID,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[PaymentMethodResp]:
    payment_method = await ctx.payment_methods_use_cases.get_payment_method().execute(
        GetPaymentMethodDTO(payment_method_id=payment_method_id),
    )

    return StdResponse(
        data=PaymentMethodResp.model_validate(payment_method),
    )


@payment_methods_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=StdResponse[PaymentMethodResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        payment_method_excs.PaymentMethodNameAlreadyExistsException,
        payment_method_excs.PaymentMethodDomainUpdateException,
    ),
    description="""
    Создание нового способа оплаты.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        CreatePaymentMethodReq:
            - name (1-120) — обязательное поле.

    Результат:
        HTTP 201.
        data содержит созданный способ оплаты.
        Поля payment_method_id, created_at, is_active (всегда true) назначаются сервером.

    Ошибки:
        401 — пользователь не авторизован.
        409 — способ оплаты с таким именем уже существует.
        422 — нарушение ограничений полей.

    Критические сценарии для API-тестов:
        1. Создание способа оплаты с валидным именем.
        2. Проверка, что созданная запись активна (isActive == true).
        3. Попытка создать способ оплаты с уже существующим именем -> 409.
        4. Проверка сохранения данных через GET по возвращенному payment_method_id.
    """,
)
async def create_payment_method(
    body: CreatePaymentMethodReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[PaymentMethodResp]:
    payment_method = await ctx.payment_methods_use_cases.create_payment_method().execute(
        CreatePaymentMethodDTO(
            actor_id=UUID(access_token_payload.employee_id),
            name=body.name,
        ),
    )

    return StdResponse(
        data=PaymentMethodResp.model_validate(payment_method),
    )


@payment_methods_router.patch(
    "/{payment_method_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[PaymentMethodResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        payment_method_excs.PaymentMethodNotFoundException,
        payment_method_excs.PaymentMethodNameAlreadyExistsException,
        payment_method_excs.PaymentMethodDomainUpdateException,
    ),
    description="""
    Обновление данных способа оплаты.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        Path: payment_method_id — UUID способа оплаты.
        Body: UpdatePaymentMethodReq (поля: name, is_active).

    Результат:
        HTTP 200.
        data содержит актуальное состояние способа оплаты.

    Ошибки:
        401 — пользователь не авторизован.
        404 — способ оплаты не найден.
        409 — новое имя уже занято другим способом оплаты.
        422 — пустое тело запроса `{}` или нарушение доменных инвариантов.

    Важные требования:
        1. Деактивация/реактивация выполняется через поле is_active.
        2. Физического удаления нет.

    Критические сценарии для API-тестов:
        1. Изменение имени способа оплаты.
        2. Деактивация активного способа оплаты (is_active: false).
        3. Реактивация деактивированного способа оплаты (is_active: true).
        4. Попытка изменить имя на уже существующее -> 409.
        5. Пустой запрос -> 422.
        6. Проверка результата через GET.
    """,
)
async def update_payment_method(
    payment_method_id: UUID,
    body: UpdatePaymentMethodReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[PaymentMethodResp]:
    payment_method = await ctx.payment_methods_use_cases.update_payment_method().execute(
        UpdatePaymentMethodDTO(
            actor_id=UUID(access_token_payload.employee_id),
            payment_method_id=payment_method_id,
            payload=body.model_dump(exclude_unset=True),
        ),
    )

    return StdResponse(
        data=PaymentMethodResp.model_validate(payment_method),
    )


@payment_methods_router.get(
    "/check-duplicate",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[PaymentMethodResp | NoneType],
    responses=map_exceptions_to_responses(UnauthorizedException),
    description="""
    Поиск дубликата способа оплаты.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        Query parameter: name (1-120).

    Логика поиска:
        1. Порог similarity: name >= 0.35.
        2. Поиск осуществляется среди всех записей (и активных, и деактивированных).
        3. Из всех подходящих кандидатов выбирается один лучший по similarity score.
        4. Порядок выбора при равном similarity: created_at DESC, payment_method_id DESC.

    Результат:
        HTTP 200.
        data содержит PaymentMethodResp (лучший кандидат) или null, если совпадений не найдено.
        Проверка является подсказкой и не блокирует создание похожего имени. Точное совпадение приводит к 409.

    Критические сценарии для API-тестов:
        1. Поиск по имени с точным совпадением -> возвращается способ оплаты.
        2. Поиск по имени с частичным совпадением выше порога (0.35) -> возвращается способ оплаты.
        3. Поиск по имени, не достигающего порога -> data == null.
        4. Поиск деактивированного способа оплаты -> возвращается способ оплаты.
    """,
)
async def check_duplicate_payment_method(
    name: Annotated[str, Query(min_length=1, max_length=120)],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[PaymentMethodResp | None]:
    payment_method = await ctx.payment_methods_use_cases.check_duplicate().execute(
        CheckPaymentMethodDuplicateDTO(name=name),
    )

    return StdResponse(
        data=(PaymentMethodResp.model_validate(payment_method) if payment_method is not None else None),
    )
