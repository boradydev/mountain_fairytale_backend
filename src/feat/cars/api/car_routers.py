from types import NoneType
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query, status

from src.feat.cars.api.car_schemas import (
    CarResp,
    CarsResp,
    CreateCarReq,
    UpdateCarReq,
)
from src.api.fastapi.common.api_excs import UnauthorizedException
from src.api.fastapi.common.deps import (
    AccessTokenPayloadDep,
    Context,
)
from src.api.fastapi.common.excs_handlers import map_exceptions_to_responses
from src.api.fastapi.common.schemas import StdResponse
from src.feat.cars.app.usecases.check_duplicate import CheckCarDuplicateDTO
from src.feat.cars.app.usecases.create import CreateCarDTO
from src.feat.cars.app.usecases.get import GetCarDTO
from src.feat.cars.app.usecases.get_all import GetCarsDTO
from src.feat.cars.app.usecases.update import UpdateCarDTO
from src.feat.cars.domain import car_excs

"""
API CONTRACT — CARS

Этот модуль является источником требований к HTTP API автомобилей.

Назначение:
    Управление автомобилями через API.

Основные правила:
    1. Автомобиль не удаляется физически.
    2. Для удаления из активного использования применяется деактивация через обновление данных (PATCH).
    3. Деактивированный автомобиль можно повторно активировать через обновление данных (PATCH).
    4. История автомобиля должна сохраняться.
    5. Госномер автомобиля должен быть уникальным.
    6. ID автомобиля является UUID.
    7. Все request/response schemas используют camelCase через BaseSchema.
    8. Все эндпоинты модуля являются защищенными (Protected) и требуют авторизации.

Авторизация:
    Токен доступа (access token) может быть передан двумя способами:
    1. Через Cookies: кука `access-token`.
    2. Через Headers (для Flutter): заголовок `Authorization: Bearer <token>`.

AI TESTING RULES:

    1. Тестировать HTTP API через публичные endpoints этого router.
    2. Не использовать use cases для определения ожидаемого поведения API.
    3. Не анализировать repositories/services для определения требований.
    4. Ожидаемое поведение определять только из:
        - router;
        - schemas;
        - domain/API exceptions;
        - APP_EXCEPTION_MAP;
        - exception handlers.
    5. Use cases, repositories и services могут содержать ошибки.
       API-тесты должны быть способны обнаруживать эти ошибки.
    6. Изменение состояния выполнять через реальные HTTP-запросы API.
    7. Данные, которые невозможно создать через API, разрешается подготавливать
       через тестовые UOW/repository fixtures.
    8. Проверять не только HTTP status code, но и тело ответа.
    9. Проверять фактическое изменение состояния после POST/PUT/PATCH.
    10. Проверять сохранение состояния автомобиля после изменения статуса активности через PATCH.
    11. Не предполагать физическое удаление автомобиля.
"""


cars_router = APIRouter(
    prefix="/app",
    tags=["Автомобили"],
)


@cars_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[CarsResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
    ),
    description="""
    Получение списка всех автомобилей.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        Query parameter:
            include_deactivated: если true, вернуть все автомобили, включая деактивированные.

    Действие:
        Вернуть список автомобилей.

    Результат:
        Если include_deactivated=false (по умолчанию) -> список только активных автомобилей.
        Если include_deactivated=true -> список всех автомобилей.

    Критические сценарии для API-тестов:
        1. Если активных автомобилей нет, а include_deactivated=false, то возвращается пустой список.
        2. При include_deactivated=false в списке только активные автомобили.
        3. При include_deactivated=true в списке присутствуют и активные, и деактивированные автомобили.
    """,
)
async def get_cars(
    ctx: Context,
    include_deactivated: Annotated[bool, Query()] = False,
) -> StdResponse[CarsResp]:
    cars = await ctx.cars_use_cases.get_cars().execute(
        GetCarsDTO(include_deactivated=include_deactivated)
    )

    return StdResponse(
        data=CarsResp(
            cars=[CarResp.model_validate(car) for car in cars],
        ),
    )


@cars_router.get(
    "/check-duplicate",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[CarResp | NoneType],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
    ),
    description="""
    Проверка существования автомобиля с указанным государственным номером.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        Query parameter:
            number: государственный номер автомобиля.

    Результат:
        Если автомобиль с таким номером существует:
            data содержит CarResp.

        Если автомобиль с таким номером отсутствует:
            data == null.

    Важные требования:
        1. Endpoint не должен возвращать 404, если автомобиль не найден.
        2. Отсутствие автомобиля является нормальным результатом проверки.
        3. Поиск выполняется по полному значению number.
        4. Поиск должен находить как активные, так и деактивированные автомобили.

    Критические сценарии для API-тестов:
        1. Номер существует -> возвращается автомобиль.
        2. Номер не существует -> data == null.
        3. После создания автомобиля проверка его номера возвращает автомобиль.
        4. Номер деактивированного автомобиля должен быть найден.
    """,
)
async def check_duplicate(
    number: Annotated[str, Query(min_length=1, max_length=30)],
    ctx: Context,
) -> StdResponse[CarResp | None]:
    car = await ctx.cars_use_cases.check_duplicate().execute(
        CheckCarDuplicateDTO(
            number=number,
        ),
    )

    return StdResponse(
        data=(CarResp.model_validate(car) if car is not None else None),
    )


@cars_router.get(
    "/{car_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[CarResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        car_excs.CarNotFoundException,
    ),
    description="""
    Получение автомобиля по UUID.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Результат:
        Автомобиль (активный или деактивированный).

    Важные требования:
        1. Получение любого существующего автомобиля независимо от его статуса.

    Критические сценарии для API-тестов:
        1. Получение существующего активного автомобиля.
        2. Получение существующего деактивированного автомобиля.
        3. Получение несуществующего автомобиля, статус код 404.
    """,
)
async def get_car(
    car_id: Annotated[UUID, Path()],
    ctx: Context,
) -> StdResponse[CarResp]:
    car = await ctx.cars_use_cases.get_car().execute(
        GetCarDTO(
            car_id=car_id,
        ),
    )

    return StdResponse(
        data=CarResp.model_validate(car),
    )


@cars_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=StdResponse[CarResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        car_excs.CarNumberAlreadyExistsException,
    ),
    description="""
    Создание нового автомобиля.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Результат:
        Содержит созданный автомобиль.

    Важные требования:
        1. Нельзя создать два автомобиля с одним number.
        2. Новый автомобиль является активным.
        3. Создание автомобиля не должно изменять существующие автомобили.

    Критические сценарии для API-тестов:
        1. Создание автомобиля с валидными данными.
        2. Проверка возвращённого carId.
        3. Проверка isActive == true.
        4. Проверка сохранения данных через GET.
        5. Попытка создать второй автомобиль с тем же number.
    """,
)
async def create_car(
    body: CreateCarReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[CarResp]:
    car = await ctx.cars_use_cases.create_car().execute(
        CreateCarDTO(
            actor_id=UUID(access_token_payload.employee_id),
            model=body.model,
            number=body.number,
            current_mileage=body.current_mileage,
        ),
    )

    return StdResponse(
        data=CarResp.model_validate(car),
    )


@cars_router.patch(
    "/{car_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[CarResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        car_excs.CarNotFoundException,
        car_excs.CarNumberAlreadyExistsException,
        car_excs.CarDomainUpdateException,
    ),
    description="""
    Обновление данных автомобиля.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Результат:
        Содержит актуальное состояние автомобиля.

    Важные требования:
        1. Изменение number не должно создавать дубликатов.
        2. Обновление одного автомобиля не должно изменять другой автомобиль.


    Критические сценарии для API-тестов:
        1. Частичное обновление полей.
        2. Полное обновление всех полей.
        3. Обновление несуществующего автомобиля -> 404 Not Found.
        4. Попытка занять уже существующий номер автомобиля -> 409 Conflict.
        5. Проверка результата через GET (что данные реально применились в БД).
        6. Пустой запрос (тело запроса `{}`): -> 422.
        7. Передача `null` в поля: если домен определит, что `null` не валиден для данного поля, возвращается 422.
        8. Передача невалидного UUID в URL: отправка `/app/123-не-uuid` -> 422.
        9. Нарушение доменных инвариантов при обновлении (CarDomainUpdateException) -> 422 Unprocessable Entity.
        10. Деактивация активного автомобиля через PATCH.
        11. Повторная активация деактивированного автомобиля через PATCH.
    """,
)
async def update_car(
    car_id: Annotated[UUID, Path()],
    body: UpdateCarReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[CarResp]:
    car = await ctx.cars_use_cases.update_car().execute(
        UpdateCarDTO(
            actor_id=UUID(access_token_payload.employee_id),
            car_id=car_id,
            payload=body.model_dump(exclude_unset=True),
        ),
    )

    return StdResponse(
        data=CarResp.model_validate(car),
    )
