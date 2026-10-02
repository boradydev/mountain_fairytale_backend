from src.presentation.fastapi.common.handlers import get_swagger_exc
from src.domain.employees.excs import EmployeeNotFoundException
from src.presentation.fastapi.auth.excs import UnauthorizedException

GET_EMPLOYEE = get_swagger_exc(
    EmployeeNotFoundException,
)


GET_EMPLOYEES = get_swagger_exc()


UPDATE_EMPLOYEE = get_swagger_exc(
    EmployeeNotFoundException,
)


DEACTIVATE_EMPLOYEE = get_swagger_exc(
    EmployeeNotFoundException,
)


CHANGE_EMPLOYEE_PASSWORD = get_swagger_exc(
    EmployeeNotFoundException,
)


CREATE_EMPLOYEE = get_swagger_exc(
    UnauthorizedException,
)
