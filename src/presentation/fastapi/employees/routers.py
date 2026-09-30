from types import NoneType

from fastapi import APIRouter, status

from src.presentation.fastapi.common.schemas import StdResponse


AUTH_TAGS = ["Авторизация и аутентификация сотрудников"]

auth_router = APIRouter(
    prefix="/auth",
    tags=AUTH_TAGS,
)


auth_router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
)(lambda: None)

auth_router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
)(lambda: None)


ME_TAGS = ["Logout сотрудника"]

me_router = APIRouter(
    prefix="/me",
    tags=ME_TAGS,
)

me_router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
)(lambda: None)


EMPLOYEES_TAGS = ["Crud сотрудников для использования админом"]

employees_router = APIRouter(
    prefix="/employees",
    tags=EMPLOYEES_TAGS,
)

employees_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
)(lambda: None)

employees_router.get(
    "/{employee_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
)(lambda: None)

employees_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=StdResponse[NoneType],
)(lambda: None)

employees_router.put(
    "/{employee_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
)(lambda: None)

employees_router.delete(
    "/{employee_id:uuid}",
    status_code=status.HTTP_200_OK,
)(lambda: None)

employees_router.put(
    "/{employee_id:uuid}/change-password",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
)(lambda: None)
