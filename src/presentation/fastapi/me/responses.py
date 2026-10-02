from src.presentation.fastapi.common.handlers import get_swagger_exc
from src.presentation.fastapi.auth.excs import UnauthorizedException
from src.domain.employees.excs import EmployeeNotFoundException

LOGOUT = get_swagger_exc(
    UnauthorizedException,
)

CHANGE_PASSWORD = get_swagger_exc(
    UnauthorizedException,
    EmployeeNotFoundException,
)
