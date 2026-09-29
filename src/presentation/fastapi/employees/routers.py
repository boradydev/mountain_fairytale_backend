from fastapi import APIRouter, status

from src.presentation.fastapi.common.schemas import StdResponse


employees_public_router = APIRouter(
    prefix="/employees",
    tags=["Авторизация и аутентификация сотрудников"],
)


employees_protected_router = APIRouter(
    prefix="/employees",
    tags=["Сотрудники"],
)


employees_public_router.post(
    "/register",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[None],
)(lambda: None)


employees_public_router.post(
    "/resend",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[None],
)(lambda: None)


employees_public_router.post(
    "/confirm",
    status_code=status.HTTP_201_CREATED,
    response_model=StdResponse[None],
)(lambda: None)


employees_public_router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[None],
)(lambda: None)


employees_public_router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[None],
)(lambda: None)


employees_protected_router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[None],
)(lambda: None)
