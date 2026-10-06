from dataclasses import dataclass
from src.core.excs import BaseAppException

@dataclass(frozen=True, slots=True)
class DriverNotFoundException(BaseAppException):
    pass

@dataclass(frozen=True, slots=True)
class DriverDomainUpdateException(BaseAppException):
    pass
