from dataclasses import dataclass

from src.core.excs import BaseAppException


@dataclass(frozen=True, slots=True)
class InvalidAccessTokenException(BaseAppException):
    pass


@dataclass(frozen=True, slots=True)
class InvalidRefreshTokenException(BaseAppException):
    pass
