"""
API CONTRACT — CLIENTS

Назначение:
    Управление клиентами через HTTP API.

Основные правила:
    1. Клиенты не удаляются физически. Для исключения клиента из активного
       использования применяется деактивация через PATCH.
    2. Деактивированного клиента можно повторно активировать через PATCH.
    3. История клиента сохраняется.
    4. Идентификаторы клиента и связанных сущностей — UUID.
    5. Все request/response schemas используют camelCase через BaseSchema.
    6. Все эндпоинты защищены авторизацией, но доступны любому
       аутентифицированному пользователю независимо от его роли.
    7. Телефон клиента уникален. Дубликат телефона приводит к HTTP 409.
    8. Для создания обязательны name, phone, address и
       sleeping_threshold_days.
    9. last_delivery_date и last_delivery_quantity nullable и возвращаются
       в ответах. Они не изменяются через API клиентов.
    10. cooldown_until, sales_representative_id и
        default_payment_method_id могут быть null.
    11. Для связанных сущностей проверяется существование записи. Связанную
        деактивированную сущность разрешено назначить клиенту.
    12. Список клиентов сортируется по created_at DESC, затем по client_id DESC.
        Параметры offset, limit и total передаются в верхнем уровне StdResponse.
    13. Проверка дубликата требует все три query-параметра: name, phone и
        address. Если хотя бы один параметр не передан или не проходит
        валидацию, API возвращает HTTP 422. Поиск рассматривает активных и
        деактивированных клиентов; кандидат должен пройти порог similarity
        минимум по двум из трёх полей.

Авторизация:
    Access token передаётся одним из способов:
    1. Через cookie `access-token`.
    2. Через заголовок `Authorization: Bearer <token>`.

AI TESTING RULES:
    1. Тестировать HTTP API через публичные endpoints этого router.
    2. Ожидаемое поведение API определять по контракту, router, schemas,
       domain/API exceptions, APP_EXCEPTION_MAP и exception handlers.
    3. Не использовать use cases и repositories для определения ожидаемого
       поведения API: API-тесты должны выявлять ошибки этих слоёв.
    4. Изменять состояние через реальные HTTP-запросы. Данные, которые
       невозможно создать через API, разрешается подготавливать через
       тестовые UOW/repository fixtures.
    5. Проверять HTTP status code и тело ответа, а после POST/PATCH —
       фактическое состояние через GET или список.
    6. Проверять пагинацию, порядок сортировки и значение total.
    7. Проверять сохранение клиента после деактивации и повторной активации.
    8. Не предполагать физическое удаление клиента.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query, status

from src.common.api.api_excs import UnauthorizedException
from src.common.api.deps import AccessTokenPayloadDep, Context
from src.common.api.excs_handlers import map_exceptions_to_responses
from src.common.api.schemas import StdResponse
from src.feat.clients.api.client_schemas import (
    ClientResp,
    ClientsResp,
    CreateClientReq,
    UpdateClientReq,
)
from src.feat.clients.app.usecases.check_duplicate import CheckClientDuplicateDTO
from src.feat.clients.app.usecases.create import CreateClientDTO
from src.feat.clients.app.usecases.get import GetClientDTO
from src.feat.clients.app.usecases.get_all import GetClientsDTO
from src.feat.clients.app.usecases.update import UpdateClientDTO
from src.feat.clients.domain import client_excs


clients_router = APIRouter(
    prefix="/clients",
    tags=["Клиенты"],
)


@clients_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[ClientsResp],
    responses=map_exceptions_to_responses(UnauthorizedException),
    description="""
    Получение списка клиентов с пагинацией.

    Предусловие:
        Запрос выполняется от имени любого аутентифицированного пользователя.

    Query-параметры:
        include_deactivated: включить ли деактивированных клиентов;
            по умолчанию false.
        offset: число записей, которые нужно пропустить; значение не меньше 0.
        limit: максимальное число записей; значение не меньше 1.

    Действие:
        Вернуть клиентов с сортировкой created_at DESC, затем client_id DESC.

    Результат:
        data.clients содержит страницу клиентов.
        offset, limit и total находятся на верхнем уровне StdResponse.
        total — количество записей, соответствующих include_deactivated,
        до применения offset и limit.

    Критические сценарии для API-тестов:
        1. По умолчанию возвращаются только активные клиенты.
        2. include_deactivated=true включает активных и деактивированных клиентов.
        3. offset и limit применяются к стабильно отсортированному списку.
        4. Пустой результат возвращается как пустой список.
        5. Некорректные значения offset и limit приводят к HTTP 422.
    """,
)
async def get_clients(
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
    include_deactivated: Annotated[bool, Query()] = False,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1)] = 100,
) -> StdResponse[ClientsResp]:
    clients, total = await ctx.clients_use_cases.get_clients().execute(
        GetClientsDTO(
            include_deactivated=include_deactivated,
            offset=offset,
            limit=limit,
        ),
    )
    return StdResponse(
        data=ClientsResp(
            clients=[ClientResp.model_validate(client) for client in clients],
        ),
        offset=offset,
        limit=limit,
        total=total,
    )


@clients_router.get(
    "/{client_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[ClientResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        client_excs.ClientNotFoundException,
    ),
    description="""
    Получение клиента по UUID.

    Предусловие:
        Запрос выполняется от имени любого аутентифицированного пользователя.

    Результат:
        Возвращается существующий клиент независимо от статуса активности.
        Если клиент не найден, возвращается HTTP 404.

    Критические сценарии для API-тестов:
        1. Получение существующего активного клиента.
        2. Получение существующего деактивированного клиента.
        3. Получение клиента с неизвестным UUID возвращает HTTP 404.
        4. Некорректный UUID в пути приводит к HTTP 422.
    """,
)
async def get_client(
    client_id: Annotated[UUID, Path()],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[ClientResp]:
    client = await ctx.clients_use_cases.get_client().execute(
        GetClientDTO(client_id=client_id),
    )
    return StdResponse(data=ClientResp.model_validate(client))


@clients_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=StdResponse[ClientResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        client_excs.ClientDomainUpdateException,
        client_excs.ClientPhoneAlreadyExistsException,
        client_excs.ClientRelatedEntityNotFoundException,
    ),
    description="""
    Создание нового активного клиента.

    Предусловие:
        Запрос выполняется от имени любого аутентифицированного пользователя.

    Обязательные поля:
        name, phone, address и sleeping_threshold_days.
        sleeping_threshold_days должен быть числом от 0 до 3650 включительно.

    Необязательные поля:
        cooldown_until, sales_representative_id и
        default_payment_method_id могут быть null.
        Если передан ID связанной сущности, запись должна существовать.
        Деактивированную связанную сущность разрешено назначить клиенту.

    Результат:
        HTTP 201 и созданный клиент. last_delivery_date и
        last_delivery_quantity у нового клиента равны null.

    Ошибки:
        HTTP 409 — телефон уже используется другим клиентом.
        HTTP 422 — ошибка доменного обновления, несуществующая связанная
        сущность или ошибка валидации запроса.

    Критические сценарии для API-тестов:
        1. Создание клиента с обязательными полями.
        2. Новый клиент активен, а поля последней доставки равны null.
        3. Возвращённый UUID позволяет получить клиента через GET.
        4. Повторное создание с существующим телефоном возвращает HTTP 409.
        5. Назначение существующей деактивированной связанной сущности разрешено.
        6. Назначение несуществующей связанной сущности приводит к HTTP 422.
        7. Отсутствие обязательного поля или нарушение ограничений схемы
           приводит к HTTP 422.
    """,
)
async def create_client(
    body: CreateClientReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[ClientResp]:
    client = await ctx.clients_use_cases.create_client().execute(
        CreateClientDTO(
            actor_id=UUID(access_token_payload.employee_id),
            name=body.name,
            phone=body.phone,
            address=body.address,
            cooldown_until=body.cooldown_until,
            sleeping_threshold_days=body.sleeping_threshold_days,
            sales_representative_id=body.sales_representative_id,
            default_payment_method_id=body.default_payment_method_id,
        ),
    )
    return StdResponse(data=ClientResp.model_validate(client))


@clients_router.patch(
    "/{client_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[ClientResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        client_excs.ClientNotFoundException,
        client_excs.ClientDomainUpdateException,
        client_excs.ClientPhoneAlreadyExistsException,
        client_excs.ClientRelatedEntityNotFoundException,
    ),
    description="""
    Частичное обновление клиента.

    Предусловие:
        Запрос выполняется от имени любого аутентифицированного пользователя.

    Действие:
        Обновляются только переданные поля. Пустое тело запроса запрещено.
        Передача null разрешена для nullable-полей, в частности для
        cooldown_until и ID связанных сущностей. Поля name, phone, address и
        sleeping_threshold_days не могут быть null.
        last_delivery_date и last_delivery_quantity через этот endpoint
        не изменяются. Для смены статуса используется is_active.

    Проверки:
        При изменении телефона он должен оставаться уникальным.
        Переданные ID связанных сущностей должны указывать на существующие
        записи; деактивированные связанные сущности допустимы.

    Результат:
        HTTP 200 и актуальное состояние клиента.
        HTTP 404 — клиент не найден.
        HTTP 409 — телефон уже занят другим клиентом.
        HTTP 422 — некорректное тело, ошибка доменного обновления или
        несуществующая связанная сущность.

    Критические сценарии для API-тестов:
        1. Частичное обновление одного поля сохраняет остальные поля.
        2. Пустой объект приводит к HTTP 422.
        3. Передача null в nullable-поля очищает соответствующее значение.
        4. Передача null в обязательные поля приводит к HTTP 422.
        5. Попытка использовать телефон другого клиента возвращает HTTP 409
           и не изменяет сохранённое состояние.
        6. PATCH неизвестного UUID возвращает HTTP 404.
        7. Деактивация и повторная активация сохраняют запись клиента.
        8. Некорректный UUID в пути приводит к HTTP 422.
    """,
)
async def update_client(
    client_id: Annotated[UUID, Path()],
    body: UpdateClientReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[ClientResp]:
    client = await ctx.clients_use_cases.update_client().execute(
        UpdateClientDTO(
            actor_id=UUID(access_token_payload.employee_id),
            client_id=client_id,
            payload=body,
        ),
    )
    return StdResponse(data=ClientResp.model_validate(client))


@clients_router.get(
    "/check-duplicate",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[ClientResp | None],
    responses=map_exceptions_to_responses(UnauthorizedException),
    description="""
    Проверка наличия клиента, похожего на переданные данные.

    Предусловие:
        Запрос выполняется от имени любого аутентифицированного пользователя.

    Query-параметры:
        Обязательны все три параметра: name, phone и address.
        name: от 1 до 120 символов.
        phone: от 1 до 32 символов.
        address: от 1 до 500 символов.
        Отсутствующий или невалидный параметр приводит к HTTP 422.

    Действие:
        Поиск выполняется среди активных и деактивированных клиентов.
        Кандидат считается совпадением, если проходит порог similarity
        минимум по двум из трёх полей.

    Результат:
        Если совпадение найдено, data содержит ClientResp.
        Если совпадение не найдено, data равен null. Отсутствие совпадения
        не является ошибкой и не приводит к HTTP 404.

    Критические сценарии для API-тестов:
        1. Точное совпадение возвращает клиента.
        2. Отсутствие совпадений возвращает HTTP 200 и data == null.
        3. Проверка находит клиента, даже если он деактивирован.
        4. Запрос без каждого из обязательных параметров приводит к HTTP 422.
        5. Пустое или слишком длинное значение параметра приводит к HTTP 422.
        6. Совпадение только по одному полю не должно считаться дубликатом.
    """,
)
async def check_duplicate_client(
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
    name: Annotated[str, Query(min_length=1, max_length=120)],
    phone: Annotated[str, Query(min_length=1, max_length=32)],
    address: Annotated[str, Query(min_length=1, max_length=500)],
) -> StdResponse[ClientResp | None]:
    client = await ctx.clients_use_cases.check_duplicate().execute(
        CheckClientDuplicateDTO(
            name=name,
            phone=phone,
            address=address,
        ),
    )
    return StdResponse(
        data=ClientResp.model_validate(client) if client is not None else None,
    )
