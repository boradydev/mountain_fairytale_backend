"""
Central registry mapping internal domain exceptions to API HTTP responses.

AI Note:
    - This map is the SINGLE SOURCE OF TRUTH for error translation.
    - Used by `get_business_exception_handler` to catch internal errors and return JSON responses.
    - Used by `get_swagger_exc` to automatically document HTTP errors in Swagger.
    - To expose a new internal exception to the API, add it here with its status code and message.
"""

from collections.abc import Mapping

from src.infra.services.token.excs import InvalidRefreshTokenException
from types import MappingProxyType

from src.api.fastapi.common.api_excs import RefreshTokenNotFoundException, UnauthorizedException, ForbiddenException
from src.api.fastapi.common.types import Resp
from src.core.excs import BaseAppException
from src.domain.auth.auth_excs import AuthEmployeeNotFoundException, InvalidCredentialsException, \
    AuthEmployeeNotFoundByUsernameException, AuthEmployeeDeactivateException
from src.feat.cars.domain.car_excs import (
    CarNotFoundException,
    CarNumberAlreadyExistsException,
    CarAlreadyActivateException,
)
from src.domain.employees.employee_excs import (
    EmployeeDeactivateException,
    EmployeeNotFoundByUsernameException,
    EmployeeNotFoundException,
    EmployeeDomainUpdateException,
    EmployeeUsernameAlreadyExistsException,
)
from src.domain.clients.client_excs import (
    ClientNotFoundException,
    ClientDomainUpdateException,
)
from src.domain.drivers.driver_excs import (
    DriverNotFoundException,
    DriverDomainUpdateException,
)
from src.domain.pay_methods.payment_method_excs import (
    PaymentMethodNotFoundException,
    PaymentMethodDomainUpdateException,
    PaymentMethodNameAlreadyExistsException,
)
from src.domain.products.product_excs import (
    ProductNotFoundException,
    ProductDomainUpdateException,
    ProductNameAlreadyExistsException,
)
from src.domain.sales_representatives.sales_representative_excs import (
    SalesRepresentativeNotFoundException,
    SalesRepresentativeDomainUpdateException,
    SalesRepresentativePhoneAlreadyExistsException,
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
        ForbiddenException: Resp(
            status_code=403,
            detail="Forbidden",
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
            detail="Car number already exists",
        ),
        CarAlreadyActivateException: Resp(
            status_code=409,
            detail="Car is already active",
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
        InvalidRefreshTokenException: Resp(
            status_code=401,
            detail="Invalid credentials",
        ),
        EmployeeDomainUpdateException: Resp(
            status_code=422,
            detail="Employee domain update error",
        ),
        EmployeeUsernameAlreadyExistsException: Resp(
            status_code=409,
            detail="Employee username already exists",
        ),
        ClientNotFoundException: Resp(
            status_code=404,
            detail="Client not found",
        ),
        ClientDomainUpdateException: Resp(
            status_code=422,
            detail="Client domain update error",
        ),
        DriverNotFoundException: Resp(
            status_code=404,
            detail="Driver not found",
        ),
        DriverDomainUpdateException: Resp(
            status_code=422,
            detail="Driver domain update error",
        ),
        PaymentMethodNotFoundException: Resp(
            status_code=404,
            detail="Payment method not found",
        ),
        PaymentMethodDomainUpdateException: Resp(
            status_code=422,
            detail="Payment method domain update error",
        ),
        PaymentMethodNameAlreadyExistsException: Resp(
            status_code=409,
            detail="Payment method name already exists",
        ),
        ProductNotFoundException: Resp(
            status_code=404,
            detail="Product not found",
        ),
        ProductDomainUpdateException: Resp(
            status_code=422,
            detail="Product domain update error",
        ),
        ProductNameAlreadyExistsException: Resp(
            status_code=409,
            detail="Product name already exists",
        ),
        SalesRepresentativeNotFoundException: Resp(
            status_code=404,
            detail="Sales representative not found",
        ),
        SalesRepresentativeDomainUpdateException: Resp(
            status_code=422,
            detail="Sales representative domain update error",
        ),
        SalesRepresentativePhoneAlreadyExistsException: Resp(
            status_code=409,
            detail="Sales representative phone already exists",
        ),
    },
)
