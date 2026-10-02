from dataclasses import dataclass

from src.core.excs import BaseAppException


@dataclass(frozen=True, slots=True)
class CookieNotFound(BaseAppException):
    pass
