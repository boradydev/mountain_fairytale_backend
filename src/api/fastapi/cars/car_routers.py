from types import NoneType
from uuid import UUID

from fastapi import APIRouter, status

from src.api.fastapi.cars.car_schemas import (
    CarResp,
    CarsResp,
    CheckCarDuplicateQuery,
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
from src.app.cars.usecases.activate import ActivateCarDTO
from src.app.cars.usecases.check_duplicate import CheckCarDuplicateDTO
from src.app.cars.usecases.create import CreateCarDTO
from src.app.cars.usecases.deactivate import DeactivateCarDTO
from src.app.cars.usecases.get import GetCarDTO
from src.app.cars.usecases.update import UpdateCarDTO
from src.domain.cars.car_excs import (
    CarNotFoundException,
    CarNumberAlreadyExistsException,
)


"""
API CONTRACT — CARS

Этот модуль является источником требований к HTTP API автомобилей.

Назначение:
    Управление автомобилями через API.

Основные правила:
    1. Автомобиль не удаляется физически.
    2. Для удаления из активного использования применяется деактивация.
    3. Деактивированный автомобиль можно повторно активировать.
    4. История автомобиля должна сохраняться.
    5. Госномер автомобиля должен быть уникальным.
    6. ID автомобиля является UUID.
    7. Все request/response schemas используют camelCase через BaseSchema.

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
    10. Проверять сохранение состояния автомобиля после deactivate/activate.
    11. Не предполагать физическое удаление автомобиля.
"""


cars_router = APIRouter(
    prefix="/cars",
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

    Действие:
        Вернуть список автомобилей.

    Результат:
        Список только активных автомобилей.

    Критические сценарии для API-тестов:
        1. Если активных автомобилей нет, то возвращается пустой список.
        2. В списке есть только активные автомобили.
    """,
)
async def get_cars(
    ctx: Context,
) -> StdResponse[CarsResp]:
    cars = await ctx.cars_use_cases.get_cars().execute()

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

    Критические сценарии для API-тестов:
        1. Номер существует -> возвращается автомобиль.
        2. Номер не существует -> data == null.
        3. После создания автомобиля проверка его номера возвращает автомобиль.
        4. Номер деактивированного автомобиля также должен корректно находиться,
           поскольку деактивация не является физическим удалением.
    """,
)
async def check_duplicate(
    query: CheckCarDuplicateQuery,
    ctx: Context,
) -> StdResponse[CarResp | None]:
    car = await ctx.cars_use_cases.check_duplicate().execute(
        CheckCarDuplicateDTO(
            number=query.number,
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
        CarNotFoundException,
    ),
    description="""
    Получение автомобиля по UUID.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        Path parameter:
            car_id: UUID автомобиля.

    Результат:
        HTTP 200.
        data содержит CarResp.

    Ошибки:
        401 — пользователь не авторизован.
        404 — автомобиль с указанным UUID не найден.

    Важные требования:
        1. Активный и деактивированный автомобиль остаются сущностями системы.
        2. Деактивация не должна приводить к тому, что GET по UUID начинает
           возвращать 404.

    Критические сценарии для API-тестов:
        1. Получение существующего автомобиля.
        2. Получение деактивированного автомобиля.
        3. Получение несуществующего UUID -> 404.
    """,
)
async def get_car(
    car_id: UUID,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
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
        CarNumberAlreadyExistsException,
    ),
    description="""
    Создание нового автомобиля.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        CreateCarReq:
            - model — обязательная строка;
            - number — обязательная строка;
            - currentMileage — необязательное значение.

    Результат:
        HTTP 201.
        data содержит созданный автомобиль.

    После создания:
        - carId должен быть назначен системой;
        - isActive должен быть true;
        - переданные model и number должны быть сохранены;
        - currentMileage должен соответствовать переданному значению
          либо значению по умолчанию, определённому API-контрактом.

    Ошибки:
        401 — пользователь не авторизован.
        Конфликт государственного номера — номер уже используется другим
        автомобилем.

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
        6. Запрос без авторизации.
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
        CarNotFoundException,
        CarNumberAlreadyExistsException,
    ),
    description="""
    Обновление данных автомобиля.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        Path:
            car_id — UUID автомобиля.

        Body:
            UpdateCarReq.
            Все изменяемые поля являются необязательными.

    Результат:
        HTTP 200.
        data содержит актуальное состояние автомобиля.

    Ошибки:
        401 — пользователь не авторизован.
        404 — автомобиль не найден.
        Конфликт государственного номера — указанный number уже принадлежит
        другому автомобилю.

    Важные требования:
        1. Можно изменять только поля, предусмотренные UpdateCarReq.
        2. Изменение number не должно создавать дубликатов.
        3. Обновление одного автомобиля не должно изменять другой автомобиль.
        4. Деактивированный автомобиль остаётся доступным для обновления,
           если это допускается текущей моделью API.

    Критические сценарии для API-тестов:
        1. Обновление model.
        2. Обновление number.
        3. Обновление currentMileage.
        4. Частичное обновление.
        5. Обновление несуществующего автомобиля -> 404.
        6. Попытка занять уже существующий number.
        7. Проверка результата через GET.
    """,
)
async def update_car(
    car_id: UUID,
    body: UpdateCarReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[CarResp]:
    car = await ctx.cars_use_cases.update_car().execute(
        UpdateCarDTO(
            actor_id=UUID(access_token_payload.employee_id),
            car_id=car_id,
            model=body.model,
            number=body.number,
            current_mileage=body.current_mileage,
        ),
    )

    return StdResponse(
        data=CarResp.model_validate(car),
    )


@cars_router.put(
    "/{car_id:uuid}/deactivate",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        CarNotFoundException,
    ),
    description="""
    Деактивация автомобиля.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        car_id — UUID автомобиля.

    Результат:
        HTTP 200.
        Автомобиль переводится в состояние isActive=false.

    Важные требования:
        1. Автомобиль НЕ удаляется физически.
        2. История автомобиля сохраняется.
        3. После деактивации автомобиль можно получить по UUID.
        4. Автомобиль можно повторно активировать.
        5. Повторная деактивация не должна физически удалять сущность.

    Ошибки:
        401 — пользователь не авторизован.
        404 — автомобиль не найден.

    Критические сценарии для API-тестов:
        1. Деактивация активного автомобиля.
        2. Проверка isActive == false через GET.
        3. Проверка сохранения carId/model/number.
        4. Повторная деактивация.
        5. Деактивация несуществующего автомобиля -> 404.
    """,
)
async def deactivate_car(
    car_id: UUID,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[NoneType]:
    await ctx.cars_use_cases.deactivate_car().execute(
        DeactivateCarDTO(
            actor_id=UUID(access_token_payload.employee_id),
            car_id=car_id,
        ),
    )

    return StdResponse(
        message="Автомобиль деактивирован.",
    )


@cars_router.put(
    "/{car_id:uuid}/activate",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        CarNotFoundException,
    ),
    description="""
    Активация автомобиля.

    Предусловие:
        Запрос выполняется от имени авторизованного пользователя.

    Входные данные:
        car_id — UUID автомобиля.

    Результат:
        HTTP 200.
        Автомобиль переводится в состояние isActive=true.

    Важные требования:
        1. Активация не создаёт новую сущность.
        2. Сохраняется исходный carId.
        3. Сохраняются model, number и currentMileage.
        4. Автомобиль после активации снова является активным.

    Ошибки:
        401 — пользователь не авторизован.
        404 — автомобиль не найден.

    Критические сценарии для API-тестов:
        1. deactivate -> activate.
        2. Проверка isActive == true после activate.
        3. Проверка сохранения всех остальных данных.
        4. Активация уже активного автомобиля.
        5. Активация несуществующего автомобиля -> 404.
    """,
)
async def activate_car(
    car_id: UUID,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[NoneType]:
    await ctx.cars_use_cases.activate_car().execute(
        ActivateCarDTO(
            actor_id=UUID(access_token_payload.employee_id),
            car_id=car_id,
        ),
    )

    return StdResponse(
        message="Автомобиль активирован.",
    )
