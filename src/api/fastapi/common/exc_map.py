"""
Central registry mapping internal domain exceptions to API HTTP responses.

AI Note:
    - This map is the SINGLE SOURCE OF TRUTH for error translation.
    - Used by `get_business_exception_handler` to catch internal errors and return JSON responses.
    - Used by `get_swagger_exc` to automatically document HTTP errors in Swagger.
    - To expose a new internal exception to the API, add it here with its status code and message.
"""

from collections.abc import Mapping

from src.domain.cars.excs import CarNotFoundException, CarNumberAlreadyExistsException
from types import MappingProxyType

from src.core.excs import BaseAppException
from src.domain.employees.employee_excs import (
    EmployeeNotFoundByUsernameException,
    EmployeeNotFoundException,
    InvalidCredentialsException, EmployeeDeactivateException,
)
from src.api.fastapi.common.api_excs import UnauthorizedException, RefreshTokenNotFoundException
from src.api.fastapi.common.types import Resp


APP_EXCEPTION_MAP: Mapping[type[BaseAppException], Resp] = MappingProxyType(
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

        CarNumberAlreadyExistsException: Resp(
            status_code=409,
            detail="Car with this number already exists",
        ),
        RefreshTokenNotFoundException: Resp(
            status_code=401,
            detail="Refresh token not found",
        ),
        EmployeeDeactivateException: Resp(
            status_code=403,
            detail="Employee account is deactivated",
        ),
        EmployeeAuthNotFoundException: Resp(
            status_code=401,
            detail="Invalid credentials",
        ),
    },
)
