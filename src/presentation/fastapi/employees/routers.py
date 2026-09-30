from types import NoneType
from typing import Annotated

from fastapi import APIRouter, status, Depends

from src.presentation.fastapi.common.deps import get_access_token_pyload
from src.presentation.fastapi.common.schemas import StdResponse
from src.presentation.fastapi.employees.schemas import AuthTokensResp, EmployeesResp, \
    EmployeeResp, \
    CredsReq, RefreshTokenReq, AccessTokenPyload

AUTH_TAGS = ["Авторизация и аутентификация сотрудников"]

auth_router = APIRouter(
    prefix="/auth",
    tags=AUTH_TAGS,
)


@auth_router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[AuthTokensResp],
)
async def login(
    body: CredsReq,
) -> StdResponse[AuthTokensResp]:
    assert CredsReq
    return StdResponse()

@auth_router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[AuthTokensResp],
)
async def refresh(
    body: RefreshTokenReq,
) -> StdResponse[AuthTokensResp]:
    assert RefreshTokenReq
    return StdResponse()


ME_TAGS = ["Logout сотрудника"]

me_router = APIRouter(
    prefix="/me",
    tags=ME_TAGS,
)

@me_router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
)
async def refresh(
    access_token_pyload: Annotated[AccessTokenPyload, Depends(get_access_token_pyload)],
    refresh_token: RefreshTokenReq,
) -> StdResponse[AuthTokensResp]:
    assert RefreshTokenReq
    return StdResponse()


EMPLOYEES_TAGS = ["Crud сотрудников для использования админом"]

employees_router = APIRouter(
    prefix="/employees",
    tags=EMPLOYEES_TAGS,
)

employees_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[EmployeesResp],
)(lambda: None)

employees_router.get(
    "/{employee_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[EmployeeResp],
)(lambda: None)

employees_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=StdResponse[EmployeeResp],
)(lambda: None)

employees_router.put(
    "/{employee_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[EmployeeResp],
)(lambda: None)

employees_router.delete(
    "/{employee_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
)(lambda: None)

employees_router.put(
    "/{employee_id:uuid}/change-password",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
)(lambda: None)
