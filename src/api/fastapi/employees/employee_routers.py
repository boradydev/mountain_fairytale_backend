from types import NoneType
from uuid import UUID

from fastapi import APIRouter, status

from src.api.fastapi.common.api_excs import UnauthorizedException
from src.api.fastapi.common.deps import (
    AccessTokenPayloadDep,
    Context,
)
from src.api.fastapi.common.excs_handlers import map_exceptions_to_responses
from src.api.fastapi.common.schemas import StdResponse
from src.api.fastapi.employees.employee_schemas import (
    ChangeEmployeePasswordReq,
    CreateEmployeeReq,
    EmployeeResp,
    EmployeesResp,
    UpdateEmployeeReq,
)
from src.app.employees.usecases.change_password import (
    ChangeEmployeePasswordDTO,
)
from src.app.employees.usecases.create import CreateEmployeeDTO
from src.app.employees.usecases.deactivate import DeactivateEmployeeDTO
from src.app.employees.usecases.get import GetEmployeeDTO
from src.app.employees.usecases.update import UpdateEmployeeDTO
from src.domain.employees.employee_excs import EmployeeNotFoundException


"""
API CONTRACT — EMPLOYEES

Этот модуль является источником требований к HTTP API сотрудников.

Назначение:
    CRUD и управление состоянием сотрудников.

Основные правила:
    1. Сотрудник не удаляется физически.
    2. Для прекращения доступа используется деактивация.
    3. Данные деактивированного сотрудника сохраняются.
    4. Деактивированный сотрудник может быть восстановлен на уровне домена,
       если для этого существует соответствующий API endpoint.
    5. ID сотрудника является UUID.
    6. Пароль никогда не возвращается API.
    7. Request/response schemas используют camelCase через BaseSchema.

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

    Результат:
        HTTP 200.
        data.employees содержит список EmployeeResp.

    Для каждого сотрудника возвращаются:
        - employeeId;
        - username;
        - role;
        - isActive;
        - createdAt.

    Пароль сотрудника не должен возвращаться API.

    Важные требования:
        1. В списке должны корректно отображаться активные и деактивированные
           сотрудники.
        2. Деактивация не означает физическое удаление сотрудника.
        3. История и идентификатор сотрудника должны сохраняться.

    Критические сценарии для API-тестов:
        1. Получение непустого списка.
        2. Проверка структуры каждого сотрудника.
        3. Проверка отсутствия password/passwordHash.
        4. Наличие деактивированного сотрудника после его деактивации.
    """,
)
async def get_employees(
    ctx: Context,
) -> StdResponse[EmployeesResp]:
    employees = await ctx.employees_use_cases.get_employees().execute()

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
        EmployeeNotFoundException,
    ),
    description="""
    Получение сотрудника по UUID.

    Входные данные:
        employee_id — UUID сотрудника.

    Результат:
        HTTP 200.
        data содержит EmployeeResp.

    Ошибки:
        404 — сотрудник с указанным UUID не найден.

    Важные требования:
        1. Деактивированный сотрудник продолжает существовать.
        2. Деактивированный сотрудник должен быть доступен по UUID.
        3. Пароль сотрудника не возвращается.

    Критические сценарии для API-тестов:
        1. Получение существующего сотрудника.
        2. Получение деактивированного сотрудника.
        3. Получение несуществующего UUID -> 404.
        4. Проверка отсутствия секретных данных.
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
    ),
    description="""
    Создание нового сотрудника.

    Предусловие:
        Запрос выполняется авторизованным пользователем.

    Входные данные:
        CreateEmployeeReq:
            - username — обязательная строка;
            - password — строка, включая возможность пустого пароля.

    Результат:
        HTTP 201.
        data содержит созданного сотрудника.

    После создания:
        - employeeId назначается системой;
        - сотрудник активен;
        - username соответствует запросу;
        - пароль не возвращается API.

    Ошибки:
        401 — пользователь не авторизован.

    Критические сценарии для API-тестов:
        1. Создание сотрудника с непустым паролем.
        2. Создание сотрудника с пустым паролем.
        3. Проверка employeeId.
        4. Проверка isActive.
        5. Проверка сохранения через GET.
        6. Проверка отсутствия password/passwordHash в ответе.
    """,
)
async def create_employee(
    body: CreateEmployeeReq,
    ctx: Context,
    access_token_pyload: AccessTokenPayloadDep,
) -> StdResponse[EmployeeResp]:
    employee = await ctx.employees_use_cases.create_employee().execute(
        CreateEmployeeDTO(
            actor_id=UUID(access_token_pyload.employee_id),
            username=body.username,
            password=body.password,
        ),
    )

    return StdResponse(
        data=EmployeeResp.model_validate(employee),
    )


@employees_router.put(
    "/{employee_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[EmployeeResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        EmployeeNotFoundException,
    ),
    description="""
    Обновление данных сотрудника.

    Предусловие:
        Запрос выполняется авторизованным пользователем.

    Входные данные:
        Path:
            employee_id — UUID сотрудника.

        Body:
            UpdateEmployeeReq.
            username является необязательным полем.

    Результат:
        HTTP 200.
        data содержит актуальное состояние сотрудника.

    Ошибки:
        401 — пользователь не авторизован.
        404 — сотрудник не найден.

    Важные требования:
        1. Изменяется только username, предусмотренный API-схемой.
        2. Другие поля сотрудника не должны изменяться этим endpoint.
        3. Пароль изменяется отдельным endpoint.
        4. Сотрудник сохраняет свой employeeId.

    Критические сценарии для API-тестов:
        1. Изменение username.
        2. Проверка результата через GET.
        3. Обновление несуществующего сотрудника -> 404.
        4. Проверка сохранения остальных данных.
    """,
)
async def update_employee(
    employee_id: UUID,
    body: UpdateEmployeeReq,
    ctx: Context,
    access_token_pyload: AccessTokenPayloadDep,
) -> StdResponse[EmployeeResp]:
    employee = await ctx.employees_use_cases.update_employee().execute(
        UpdateEmployeeDTO(
            actor_id=UUID(access_token_pyload.employee_id),
            employee_id=employee_id,
            username=body.username,
        ),
    )

    return StdResponse(
        data=EmployeeResp.model_validate(employee),
    )


@employees_router.delete(
    "/{employee_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        EmployeeNotFoundException,
    ),
    description="""
    Деактивация сотрудника.

    Несмотря на HTTP DELETE, операция НЕ удаляет сотрудника физически.

    Предусловие:
        Запрос выполняется авторизованным пользователем.

    Входные данные:
        employee_id — UUID сотрудника.

    Результат:
        HTTP 200.
        message:
            "Сотрудник деактивирован."

    Важные требования:
        1. Сотрудник не удаляется из базы данных.
        2. employeeId сохраняется.
        3. История сотрудника сохраняется.
        4. isActive становится false.
        5. Данные сотрудника остаются доступными для получения.

    Ошибки:
        401 — пользователь не авторизован.
        404 — сотрудник не найден.

    Критические сценарии для API-тестов:
        1. Деактивация активного сотрудника.
        2. GET после деактивации.
        3. Проверка isActive == false.
        4. Проверка сохранения employeeId и username.
        5. Деактивация несуществующего сотрудника -> 404.
    """,
)
async def deactivate_employee(
    employee_id: UUID,
    ctx: Context,
    access_token_pyload: AccessTokenPayloadDep,
) -> StdResponse[NoneType]:
    await ctx.employees_use_cases.deactivate_employee().execute(
        DeactivateEmployeeDTO(
            actor_id=UUID(access_token_pyload.employee_id),
            employee_id=employee_id,
        ),
    )

    return StdResponse(
        message="Сотрудник деактивирован.",
    )


@employees_router.put(
    "/{employee_id:uuid}/change-password",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        EmployeeNotFoundException,
    ),
    description="""
    Изменение пароля сотрудника.

    Предусловие:
        Запрос выполняется авторизованным пользователем.

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
        2. Изменение пароля не должно менять employeeId.
        3. Изменение пароля не должно менять username, role или isActive.

    Ошибки:
        401 — пользователь не авторизован.
        404 — сотрудник не найден.

    Критические сценарии для API-тестов:
        1. Изменение пароля существующего сотрудника.
        2. Изменение на пустой пароль, если схема допускает такое значение.
        3. Попытка изменить пароль несуществующего сотрудника -> 404.
        4. Проверка, что старый пароль больше не используется,
           если тестовый контракт авторизации это проверяет.
        5. Проверка, что остальные поля сотрудника не изменились.
    """,
)
async def change_employee_password(
    employee_id: UUID,
    body: ChangeEmployeePasswordReq,
    ctx: Context,
    access_token_pyload: AccessTokenPayloadDep,
) -> StdResponse[NoneType]:
    await ctx.employees_use_cases.change_employee_password().execute(
        ChangeEmployeePasswordDTO(
            actor_id=UUID(access_token_pyload.employee_id),
            employee_id=employee_id,
            password=body.password,
        ),
    )

    return StdResponse(
        message="Пароль сотрудника изменён.",
    )
