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

from src.core.excs import BaseAppException
from src.domain.employees.excs import (
    EmployeeNotFoundByUsernameException,
    EmployeeNotFoundException,
    InvalidCredentialsException,
)
from src.presentation.fastapi.common.types import Resp


APP_EXCEPTION_MAP: Mapping[type[BaseAppException], Resp] = MappingProxyType(
    {
        InvalidCredentialsException: Resp(
            status_code=401,
            detail="Invalid credentials",
        ),
        EmployeeNotFoundByUsernameException: Resp(
            status_code=404,
            detail="Employee not found",
        ),
        EmployeeNotFoundException: Resp(
            status_code=404,
            detail="Employee not found",
        ),
    },
)
