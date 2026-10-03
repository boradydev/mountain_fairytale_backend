from types import NoneType
from uuid import UUID

from fastapi import APIRouter, status

from src.app.employees.usecases.change_password import (
    ChangeEmployeePasswordDTO,
)
from src.app.employees.usecases.create import CreateEmployeeDTO
from src.app.employees.usecases.deactivate import DeactivateEmployeeDTO
from src.app.employees.usecases.get import GetEmployeeDTO
from src.app.employees.usecases.update import UpdateEmployeeDTO
from src.presentation.fastapi.common.deps import (
    AccessTokenPayloadDep,
    Context,
)
from src.presentation.fastapi.common.schemas import StdResponse
from src.presentation.fastapi.employees.schemas import (
    ChangeEmployeePasswordReq,
    CreateEmployeeReq,
    EmployeeResp,
    EmployeesResp,
    UpdateEmployeeReq,
)
from src.domain.employees.excs import EmployeeNotFoundException
from src.presentation.fastapi.auth.excs import UnauthorizedException
from src.presentation.fastapi.common.handlers import map_exceptions_to_responses

GET_EMPLOYEE_RESPONSES = map_exceptions_to_responses(EmployeeNotFoundException)
GET_EMPLOYEES_RESPONSES = map_exceptions_to_responses()
UPDATE_EMPLOYEE_RESPONSES = map_exceptions_to_responses(EmployeeNotFoundException)
DEACTIVATE_EMPLOYEE_RESPONSES = map_exceptions_to_responses(EmployeeNotFoundException)
CHANGE_EMPLOYEE_PASSWORD_RESPONSES = map_exceptions_to_responses(EmployeeNotFoundException)
CREATE_EMPLOYEE_RESPONSES = map_exceptions_to_responses(UnauthorizedException)

employees_router = APIRouter(
    prefix="/employees",
    tags=["Crud сотрудников для использования админом"],
)


@employees_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[EmployeesResp],
    responses=GET_EMPLOYEES_RESPONSES,
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
    responses=GET_EMPLOYEE_RESPONSES,
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
    responses=CREATE_EMPLOYEE_RESPONSES,
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
    responses=UPDATE_EMPLOYEE_RESPONSES,
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
    responses=DEACTIVATE_EMPLOYEE_RESPONSES,
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
    responses=CHANGE_EMPLOYEE_PASSWORD_RESPONSES,
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
