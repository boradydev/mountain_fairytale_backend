from dataclasses import dataclass
from src.core.excs import BaseAppException

@dataclass(frozen=True, slots=True)
class PaymentMethodNotFoundException(BaseAppException):
    pass

@dataclass(frozen=True, slots=True)
class PaymentMethodDomainUpdateException(BaseAppException):
    pass

@dataclass(frozen=True, slots=True)
class PaymentMethodNameAlreadyExistsException(BaseAppException):
    pass
