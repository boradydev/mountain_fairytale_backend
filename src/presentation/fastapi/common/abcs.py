from abc import ABC, abstractmethod
from typing import Any

from src.presentation.fastapi.employees.schemas import (
    AccessTokenPyload,
    RefreshTokenPyload,
)


class ITokenService(ABC):
    @abstractmethod
    def create_access_token(
        self,
        **payload: Any,
    ) -> str:
        """Создает access token с переданным payload."""
        raise NotImplementedError

    @abstractmethod
    def get_payload_access_token(
        self,
        access_token: str,
    ) -> AccessTokenPyload:
        """Проверяет access token и возвращает его payload."""
        raise NotImplementedError

    @abstractmethod
    def create_refresh_token(
        self,
        **payload: Any,
    ) -> str:
        """Создает refresh token с переданным payload."""
        raise NotImplementedError

    @abstractmethod
    def get_payload_refresh_token(
        self,
        refresh_token: str,
    ) -> RefreshTokenPyload:
        """Проверяет refresh token и возвращает его payload."""
        raise NotImplementedError
