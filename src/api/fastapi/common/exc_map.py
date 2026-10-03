"""
Central registry mapping internal domain exceptions to API HTTP responses.

AI Note:
    - This map is the SINGLE SOURCE OF TRUTH for error translation.
    - Used by `get_business_exception_handler` to catch internal errors and return JSON responses.
    - Used by `get_swagger_exc` to automatically document HTTP errors in Swagger.
    - To expose a new internal exception to the API, add it here with its status code and message.
"""

from collections.abc import Mapping
from types import MappingProxyType

from src.api.fastapi.common.api_excs import RefreshTokenNotFoundException, UnauthorizedException
from src.api.fastapi.common.types import Resp
from src.core.excs import BaseAppException
from src.domain.auth.auth_excs import AuthEmployeeNotFoundException, InvalidCredentialsException, \
    AuthEmployeeNotFoundByUsernameException, AuthEmployeeDeactivateException
from src.domain.cars.excs import CarNotFoundException
from src.domain.employees.employee_excs import (
    EmployeeDeactivateException,
    EmployeeNotFoundByUsernameException,
    EmployeeNotFoundException,
)


APP_EXCEPTION_MAP: Mapping[type[BaseAppException], Resp] = MappingProxyType(
    # AI Note: Не объединять исключения из auth_excs и employee_excs.
    # Разные доменные области -> разные HTTP-ответы (например, 401 vs 404)
    # для защиты от перебора пользователей (User Enumeration).
    {
        InvalidCredentialsException: Resp(
            status_code=401,
            detail="Invalid credentials",
        ),
        UnauthorizedException: Resp(
            status_code=401,
            detail="Unauthorized",
        ),
        EmployeeNotFoundByUsernameException: Resp(
            status_code=404,
            detail="Employee not found",
        ),
        EmployeeNotFoundException: Resp(
            status_code=404,
            detail="Employee not found",
        ),
        CarNotFoundException: Resp(
            status_code=404,
            detail="Car not found",
        ),
        RefreshTokenNotFoundException: Resp(
            status_code=401,
            detail="Refresh token not found",
        ),
        EmployeeDeactivateException: Resp(
            status_code=403,
            detail="Employee account is deactivated",
        ),
        AuthEmployeeNotFoundByUsernameException: Resp(
            status_code=401,
            detail="Invalid credentials",
        ),
        AuthEmployeeDeactivateException: Resp(
            status_code=403,
            detail="Employee account is deactivated",
        ),
        AuthEmployeeNotFoundException: Resp(
            status_code=401,
            detail="Invalid credentials",
        ),
    },
)
