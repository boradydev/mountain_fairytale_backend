from dataclasses import dataclass
from src.core.excs import BaseAppException

@dataclass(frozen=True, slots=True)
class ProductNotFoundException(BaseAppException):
    pass

@dataclass(frozen=True, slots=True)
class ProductDomainUpdateException(BaseAppException):
    pass

@dataclass(frozen=True, slots=True)
class ProductNameAlreadyExistsException(BaseAppException):
    pass
