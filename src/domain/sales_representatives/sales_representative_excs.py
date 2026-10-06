from dataclasses import dataclass
from src.core.excs import BaseAppException

@dataclass(frozen=True, slots=True)
class SalesRepresentativeNotFoundException(BaseAppException):
    pass

@dataclass(frozen=True, slots=True)
class SalesRepresentativeDomainUpdateException(BaseAppException):
    pass

@dataclass(frozen=True, slots=True)
class SalesRepresentativePhoneAlreadyExistsException(BaseAppException):
    pass
