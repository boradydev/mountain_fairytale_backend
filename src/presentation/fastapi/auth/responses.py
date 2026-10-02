"""Модуль для формирования openapi fastapi responses."""

from src.domain.employees.excs import InvalidCredentialsException, \
    EmployeeNotFoundByUsernameException
from src.presentation.fastapi.common.handlers import get_swagger_exc


LOGIN = get_swagger_exc(
    InvalidCredentialsException,
    EmployeeNotFoundByUsernameException,
)

REFRESH = get_swagger_exc(
    InvalidCredentialsException,
    EmployeeNotFoundByUsernameException,
)
