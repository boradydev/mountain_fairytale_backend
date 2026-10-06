from dataclasses import dataclass
from src.core.excs import BaseAppException

@dataclass(frozen=True, slots=True)
class ClientNotFoundException(BaseAppException):
    pass

@dataclass(frozen=True, slots=True)
class ClientDomainUpdateException(BaseAppException):
    pass
