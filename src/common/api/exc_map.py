"""
Central registry mapping internal domain exceptions to API HTTP responses.

AI Note:
    - This map is the SINGLE SOURCE OF TRUTH for error translation.
    - Used by `get_business_exception_handler` to catch internal errors and return JSON responses.
    - Used by `get_swagger_exc` to automatically document HTTP errors in Swagger.
    - To expose a new internal exception to the API, add it here with its status code and message.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from src.common.api.api_excs import (
    ForbiddenException,
    RefreshTokenNotFoundException,
    UnauthorizedException,
)
from src.common.infra.services.token.excs import InvalidAccessTokenException, InvalidRefreshTokenException
from src.core.excs import BaseAppException
from src.feat.audit_event.domain.audit_excs import InvalidAuditCursorException
from src.feat.auth.domain.auth_excs import (
    AuthEmployeeDeactivateException,
    AuthEmployeeNotFoundByUsernameException,
    AuthEmployeeNotFoundException,
    InvalidCredentialsException,
)
from src.feat.cars.domain.car_excs import (
    CarAlreadyActivateException,
    CarDomainUpdateException,
    CarNotFoundException,
    CarNumberAlreadyExistsException,
)
from src.feat.clients.domain.client_excs import (
    ClientDomainUpdateException,
    ClientNotFoundException,
    ClientPhoneAlreadyExistsException,
    ClientRelatedEntityNotFoundException,
)
from src.feat.clients.domain.location_excs import (
    GeoQuotaExceeded,
    GeoUnavailable,
    InvalidGeoResponse,
    MissingClientLocation,
)
from src.feat.commissions.domain.commission_excs import (
    InactiveCommissionTargetException,
    SameCommissionTargetException,
)
from src.feat.delivery_document.domain.delivery_document_excs import (
    DeliveryDocumentCancelledException,
    DeliveryDocumentEditLockNotFoundException,
    DeliveryDocumentEditLockNotOwnedException,
    DeliveryDocumentLockedException,
    DeliveryDocumentNotFoundException,
    DeliveryDocumentPointClientAlreadyExistsException,
    DeliveryDocumentPointProductAlreadyExistsException,
    DeliveryDocumentRelatedEntityNotFoundException,
    DeliveryDocumentUpdateException,
)
from src.feat.drivers.domain.driver_excs import (
    DriverDomainUpdateException,
    DriverNotFoundException,
)
from src.feat.employees.domain.employee_excs import (
    EmployeeDeactivateException,
    EmployeeDomainUpdateException,
    EmployeeNotFoundByUsernameException,
    EmployeeNotFoundException,
    EmployeeUsernameAlreadyExistsException,
)
from src.feat.pay_methods.domain.pay_method_excs import (
    PaymentMethodDomainUpdateException,
    PaymentMethodNameAlreadyExistsException,
    PaymentMethodNotFoundException,
)
from src.feat.products.domain.product_excs import (
    ProductDomainUpdateException,
    ProductNameAlreadyExistsException,
    ProductNotFoundException,
)
from src.feat.sales_rep.domain.sales_rep_excs import (
    SalesRepresentativeDomainUpdateException,
    SalesRepresentativeNotFoundException,
    SalesRepresentativePhoneAlreadyExistsException,
)


@dataclass(frozen=True, slots=True)
class Resp:
    status_code: int
    detail: str
    extra_fields: Callable[[Any], Mapping[str, object]] | None = None
    openapi_schema: Mapping[str, object] | None = None


APP_EXCEPTION_MAP: Mapping[type[BaseAppException], Resp] = MappingProxyType(
    {
        InactiveCommissionTargetException: Resp(status_code=409, detail="Target representative is deactivated"),
        SameCommissionTargetException: Resp(status_code=422, detail="Source and target representative must differ"),
        InvalidAuditCursorException: Resp(status_code=422, detail="Invalid event cursor"),
        InvalidCredentialsException: Resp(status_code=401, detail="Invalid credentials"),
        UnauthorizedException: Resp(status_code=401, detail="Unauthorized"),
        InvalidAccessTokenException: Resp(status_code=401, detail="Unauthorized"),
        ForbiddenException: Resp(status_code=403, detail="Forbidden"),
        EmployeeNotFoundByUsernameException: Resp(status_code=404, detail="Employee not found"),
        EmployeeNotFoundException: Resp(status_code=404, detail="Employee not found"),
        CarNotFoundException: Resp(status_code=404, detail="Car not found"),
        CarNumberAlreadyExistsException: Resp(status_code=409, detail="Car number already exists"),
        CarAlreadyActivateException: Resp(status_code=409, detail="Car is already active"),
        CarDomainUpdateException: Resp(status_code=422, detail="Car domain update error"),
        RefreshTokenNotFoundException: Resp(status_code=401, detail="Refresh token not found"),
        EmployeeDeactivateException: Resp(status_code=403, detail="Employee account is deactivated"),
        AuthEmployeeNotFoundByUsernameException: Resp(status_code=401, detail="Invalid credentials"),
        AuthEmployeeDeactivateException: Resp(status_code=403, detail="Employee account is deactivated"),
        AuthEmployeeNotFoundException: Resp(status_code=401, detail="Invalid credentials"),
        InvalidRefreshTokenException: Resp(status_code=401, detail="Invalid credentials"),
        EmployeeDomainUpdateException: Resp(status_code=422, detail="Employee domain update error"),
        EmployeeUsernameAlreadyExistsException: Resp(status_code=409, detail="Employee username already exists"),
        GeoUnavailable: Resp(status_code=503, detail="Геосервис недоступен. Повторите попытку позже."),
        GeoQuotaExceeded: Resp(status_code=429, detail="Лимит геосервиса исчерпан."),
        InvalidGeoResponse: Resp(status_code=502, detail="Геосервис вернул неполный или некорректный результат."),
        MissingClientLocation: Resp(status_code=422, detail="У одного из клиентов нет подтверждённых координат."),
        ClientNotFoundException: Resp(status_code=404, detail="Client not found"),
        ClientDomainUpdateException: Resp(status_code=422, detail="Client domain update error"),
        ClientPhoneAlreadyExistsException: Resp(status_code=409, detail="Client phone already exists"),
        ClientRelatedEntityNotFoundException: Resp(status_code=422, detail="Client related entity not found"),
        DeliveryDocumentNotFoundException: Resp(status_code=404, detail="Delivery document not found"),
        DeliveryDocumentCancelledException: Resp(status_code=409, detail="Delivery document is cancelled"),
        DeliveryDocumentUpdateException: Resp(status_code=422, detail="Delivery document update error"),
        DeliveryDocumentRelatedEntityNotFoundException: Resp(
            status_code=422,
            detail="Delivery document related entity not found",
        ),
        DeliveryDocumentPointClientAlreadyExistsException: Resp(
            status_code=422,
            detail="Client already exists in delivery document",
        ),
        DeliveryDocumentPointProductAlreadyExistsException: Resp(
            status_code=422,
            detail="Product already exists in delivery document point",
        ),
        DeliveryDocumentLockedException: Resp(
            status_code=423,
            detail="Delivery document is locked by another employee",
            extra_fields=lambda exc: {"ownerName": exc.owner_name},
            openapi_schema={
                "type": "object",
                "properties": {
                    "detail": {"type": "string"},
                    "ownerName": {"type": "string"},
                },
                "required": ["detail", "ownerName"],
            },
        ),
        DeliveryDocumentEditLockNotFoundException: Resp(
            status_code=409,
            detail="Delivery document edit lock not found or expired",
        ),
        DeliveryDocumentEditLockNotOwnedException: Resp(
            status_code=403,
            detail="Delivery document edit lock is not owned by the current employee",
        ),
        DriverNotFoundException: Resp(status_code=404, detail="Driver not found"),
        DriverDomainUpdateException: Resp(status_code=422, detail="Driver domain update error"),
        PaymentMethodNotFoundException: Resp(status_code=404, detail="Payment method not found"),
        PaymentMethodDomainUpdateException: Resp(status_code=422, detail="Payment method domain update error"),
        PaymentMethodNameAlreadyExistsException: Resp(status_code=409, detail="Payment method name already exists"),
        ProductNotFoundException: Resp(status_code=404, detail="Product not found"),
        ProductDomainUpdateException: Resp(status_code=422, detail="Product domain update error"),
        ProductNameAlreadyExistsException: Resp(status_code=409, detail="Product name already exists"),
        SalesRepresentativeNotFoundException: Resp(status_code=404, detail="Sales representative not found"),
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
