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
from src.domain.employees.employee_excs import EmployeeNotFoundException
from src.api.fastapi.common.api_excs import UnauthorizedException
from src.api.fastapi.common.deps import (
    AccessTokenPayloadDep,
    Context,
)
from src.api.fastapi.common.excs_handlers import map_exceptions_to_responses
from src.api.fastapi.common.schemas import StdResponse
from src.api.fastapi.employees.schemas import (
    ChangeEmployeePasswordReq,
    CreateEmployeeReq,
    EmployeeResp,
    EmployeesResp,
    UpdateEmployeeReq,
)


employees_router = APIRouter(
    prefix="/employees",
    tags=["Crud сотрудников для использования админом"],
)


@employees_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[EmployeesResp],
    responses=map_exceptions_to_responses(),
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
    responses=map_exceptions_to_responses(EmployeeNotFoundException),
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
    responses=map_exceptions_to_responses(UnauthorizedException),
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
    responses=map_exceptions_to_responses(EmployeeNotFoundException),
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
    responses=map_exceptions_to_responses(EmployeeNotFoundException),
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
    responses=map_exceptions_to_responses(EmployeeNotFoundException),
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
