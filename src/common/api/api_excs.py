from dataclasses import dataclass

from src.core.excs import BaseAppException


@dataclass(frozen=True, slots=True)
class UnauthorizedException(BaseAppException):
    pass


@dataclass(frozen=True, slots=True)
class RefreshTokenNotFoundException(BaseAppException):
    pass


@dataclass(frozen=True, slots=True)
class ForbiddenException(BaseAppException):
    pass
