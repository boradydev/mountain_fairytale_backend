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
from src.feat.employees.api.employee_schemas import (
    ChangeEmployeePasswordReq,
    CreateEmployeeReq,
    EmployeeResp,
    EmployeesResp,
    UpdateEmployeeReq,
)
from src.feat.employees.app.usecases.change_password import (
    ChangeEmployeePasswordDTO,
)
from src.feat.employees.app.usecases.create import CreateEmployeeDTO
from src.feat.employees.app.usecases.get import GetEmployeeDTO
from src.feat.employees.app.usecases.get_all import GetEmployeesDTO
from src.feat.employees.app.usecases.update import UpdateEmployeeDTO
from src.feat.employees.domain import employee_excs

"""
API CONTRACT — EMPLOYEES

Этот модуль является источником требований к HTTP API сотрудников.

Назначение:
    CRUD и управление состоянием сотрудников.

Основные правила:
    1. Доступ ко всем эндпоинтам этого модуля имеет только пользователь с ролью 'admin'.
    2. Сотрудник не удаляется физически.
    3. Для управления статусом доступа (активация/деактивация) используется обновление данных (PATCH).
    4. Данные деактивированного сотрудника сохраняются.
    5. ID сотрудника является UUID.
    6. Пароль никогда не возвращается API.
    7. Request/response schemas используют camelCase через BaseSchema.
    8. Поле commissionPercent входит в ответ сотрудника для всех ролей, включая администратора.
    9. commissionPercent обязательно при создании и должно быть в диапазоне 0–100.
    10. commissionPercent можно изменять через PATCH; допустимый диапазон — 0–100.

Авторизация:
    Токен доступа (access token) может быть передан двумя способами:
    1. Через Cookies: кука `access-token`.
    2. Через Headers (для Flutter): заголовок `Authorization: Bearer <token>`.

AI TESTING RULES:

    1. Тестировать HTTP API через endpoints этого router.
    2. Не использовать use cases для определения ожидаемого поведения.
    3. Не анализировать repositories/services для определения требований.
    4. Ожидаемое поведение определять только из:
        - router;
        - schemas;
        - domain exceptions;
        - APP_EXCEPTION_MAP;
        - exception handlers.
    5. Use cases, repositories и services могут содержать ошибки.
       API-тесты должны быть способны обнаруживать такие ошибки.
    6. Изменение состояния выполнять через HTTP API.
    7. Подготовку данных выполнять через test UOW/repository fixtures,
       если соответствующего API endpoint для подготовки данных нет.
    8. Проверять HTTP status code и тело ответа.
    9. Проверять состояние сущности после изменения через GET.
    10. Не считать HTTP 200 доказательством корректности операции:
        необходимо проверить фактическое состояние данных.
"""


employees_router = APIRouter(
    prefix="/employees",
    tags=["Crud сотрудников для использования админом"],
)


@employees_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[EmployeesResp],
    responses=map_exceptions_to_responses(),
    description="""
    Получение списка сотрудников.

    Предусловие:
        Запрос выполняется от имени администратора.

    Входные данные:
        Query parameter:
            include_deactivated: если true, вернуть всех сотрудников, включая деактивированных.

    Результат:
        HTTP 200.
        data.employees содержит список EmployeeResp.
        commissionPercent входит в ответ для каждого сотрудника, включая сотрудников с ролью admin.

    Важные требования:
        1. Если include_deactivated=false (по умолчанию) -> список только активных сотрудников.
        2. Если include_deactivated=true -> список всех сотрудников.
        3. Пароль сотрудника не должен возвращаться API.

    Критические сценарии для API-тестов:
        1. Получение списка только активных сотрудников.
        2. Получение списка всех сотрудников (включая деактивированных).
        3. Проверка отсутствия password/passwordHash в ответе.
        4. Проверка наличия commissionPercent в ответе каждого сотрудника.
    """,
)
async def get_employees(
    ctx: Context,
    include_deactivated: Annotated[bool, Query()] = False,
) -> StdResponse[EmployeesResp]:
    employees = await ctx.employees_use_cases.get_employees().execute(
        GetEmployeesDTO(include_deactivated=include_deactivated)
    )

    return StdResponse(
        data=EmployeesResp(
            employees=[EmployeeResp.model_validate(employee) for employee in employees],
        ),
    )


@employees_router.get(
    "/{employee_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[EmployeeResp],
    responses=map_exceptions_to_responses(
        employee_excs.EmployeeNotFoundException,
    ),
    description="""
    Получение сотрудника по UUID.

    Предусловие:
        Запрос выполняется от имени администратора.

    Входные данные:
        employee_id — UUID сотрудника.

    Результат:
        HTTP 200.
        data содержит EmployeeResp, включая commissionPercent.

    Ошибки:
        404 — сотрудник с указанным UUID не найден.

    Важные требования:
        1. Деактивированный сотрудник продолжает существовать и должен быть доступен по UUID.
        2. Пароль сотрудника не возвращается.
        3. commissionPercent возвращается для сотрудников всех ролей, включая администратора.

    Критические сценарии для API-тестов:
        1. Получение существующего активного сотрудника.
        2. Получение существующего деактивированного сотрудника.
        3. Получение несуществующего UUID -> 404.
        4. Проверка наличия commissionPercent в ответе.
    """,
)
async def get_employee(
    employee_id: UUID,
    ctx: Context,
) -> StdResponse[EmployeeResp]:
    employee = await ctx.employees_use_cases.get_employee().execute(
        GetEmployeeDTO(
            employee_id=employee_id,
        ),
    )

    return StdResponse(
        data=EmployeeResp.model_validate(employee),
    )


@employees_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=StdResponse[EmployeeResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        employee_excs.EmployeeUsernameAlreadyExistsException,
    ),
    description="""
    Создание нового сотрудника.

    Предусловие:
        Запрос выполняется администратором.

    Входные данные:
        CreateEmployeeReq:
            - username — обязательная строка;
            - password — строка, включая возможность пустого пароля;
            - commissionPercent — обязательное число типа float в диапазоне 0–100.

    Результат:
        HTTP 201.
        data содержит созданного сотрудника, включая commissionPercent.

    После создания:
        - employeeId назначается системой;
        - сотрудник активен;
        - username и commissionPercent соответствуют запросу;
        - пароль не возвращается API.

    Ошибки:
        401 — пользователь не авторизован.
        409 — username уже занят другим сотрудником.
        422 — отсутствует commissionPercent или нарушены ограничения полей.

    Критические сценарии для API-тестов:
        1. Создание сотрудника с непустым паролем и commissionPercent в диапазоне 0–100.
        2. Создание сотрудника с пустым паролем и валидным commissionPercent.
        3. Отсутствие commissionPercent -> 422.
        4. commissionPercent ниже 0 или выше 100 -> 422.
        5. Проверка employeeId и commissionPercent в ответе.
        6. Проверка isActive == true.
        7. Проверка сохранения через GET.
        8. Попытка создать сотрудника с уже существующим username -> 409.
    """,
)
async def create_employee(
    body: CreateEmployeeReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[EmployeeResp]:
    employee = await ctx.employees_use_cases.create_employee().execute(
        CreateEmployeeDTO(
            actor_id=UUID(access_token_payload.employee_id),
            username=body.username,
            password=body.password,
            commission_percent=body.commission_percent,
        ),
    )

    return StdResponse(
        data=EmployeeResp.model_validate(employee),
    )


@employees_router.patch(
    "/{employee_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[EmployeeResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        employee_excs.EmployeeNotFoundException,
        employee_excs.EmployeeDomainUpdateException,
        employee_excs.EmployeeUsernameAlreadyExistsException,
    ),
    description="""
    Обновление данных сотрудника.

    Предусловие:
        Запрос выполняется администратором.

    Входные данные:
        Path:
            employee_id — UUID сотрудника.

        Body:
            UpdateEmployeeReq.
            Поля: username, commissionPercent, is_active.
            commissionPercent можно изменять через PATCH; допустимый диапазон — 0–100.

    Результат:
        HTTP 200.
        data содержит актуальное состояние сотрудника, включая commissionPercent.

    Ошибки:
        401 — пользователь не авторизован.
        404 — сотрудник не найден.
        409 — новый username уже занят другим сотрудником.
        422 — пустое тело запроса `{}` или нарушение ограничений полей, включая диапазон commissionPercent.

    Важные требования:
        1. Изменяются только поля, предусмотренные API-схемой.
        2. Деактивация и повторная активация сотрудника происходят через изменение поля is_active.
        3. Сотрудник сохраняет свой employeeId.
        4. commissionPercent можно изменять на значение от 0 до 100 включительно.

    Критические сценарии для API-тестов:
        1. Изменение username.
        2. Изменение commissionPercent с проверкой ответа и результата через GET.
        3. commissionPercent ниже 0 или выше 100 -> 422.
        4. Деактивация активного сотрудника (is_active: false).
        5. Реактивация деактивированного сотрудника (is_active: true).
        6. Обновление несуществующего сотрудника -> 404.
        7. Пустой запрос (тело `{}`) -> 422.
        8. Изменение username на уже существующий -> 409.
    """,
)
async def update_employee(
    employee_id: UUID,
    body: UpdateEmployeeReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[EmployeeResp]:
    employee = await ctx.employees_use_cases.update_employee().execute(
        UpdateEmployeeDTO(
            actor_id=UUID(access_token_payload.employee_id),
            employee_id=employee_id,
            payload=body,
        ),
    )

    return StdResponse(
        data=EmployeeResp.model_validate(employee),
    )


@employees_router.put(
    "/{employee_id:uuid}/change-password",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        employee_excs.EmployeeNotFoundException,
    ),
    description="""
    Изменение пароля сотрудника.

    Предусловие:
        Запрос выполняется администратором.

    Входные данные:
        Path:
            employee_id — UUID сотрудника.

        Body:
            ChangeEmployeePasswordReq:
                password — новый пароль.

    Результат:
        HTTP 200.
        message:
            "Пароль сотрудника изменён."

    Важные требования:
        1. Пароль не возвращается API.
        2. Изменение пароля не должно менять employeeId, username, role, commissionPercent или isActive.

    Ошибки:
        401 — пользователь не авторизован.
        404 — сотрудник не найден.

    Критические сценарии для API-тестов:
        1. Изменение пароля существующего сотрудника.
        2. Изменение на пустой пароль.
        3. Попытка изменить пароль несуществующего сотрудника -> 404.
        4. Проверка, что остальные поля сотрудника не изменились.
    """,
)
async def change_employee_password(
    employee_id: UUID,
    body: ChangeEmployeePasswordReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[NoneType]:
    await ctx.employees_use_cases.change_employee_password().execute(
        ChangeEmployeePasswordDTO(
            actor_id=UUID(access_token_payload.employee_id),
            employee_id=employee_id,
            password=body.password,
        ),
    )

    return StdResponse(
        message="Пароль сотрудника изменён.",
    )
