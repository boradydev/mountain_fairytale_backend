from abc import ABC, abstractmethod
from datetime import datetime

from src.presentation.fastapi.employees.schemas import AccessTokenPyload, RefreshTokenPyload


class ITokenService(ABC):
    @abstractmethod
    def create_access_token(
        self,
        expires_at: datetime,
        **kwargs,
    ) -> str:
        """Создает токен доступа с полезной нагрузкой из переданных данных."""
        raise NotImplementedError

    @abstractmethod
    def get_payload_access_token(
        self,
        access_token: str,
    ) -> AccessTokenPyload:
        """Возвращает payload токена доступа в виде dataclass."""
        raise NotImplementedError

    @abstractmethod
    def create_refresh_token(
        self,
        expires_at: datetime,
        **kwargs,
    ) -> str:
        """Создает токен обновления с полезной нагрузкой из переданных данных."""
        raise NotImplementedError

    @abstractmethod
    def get_payload_refresh_token(
        self,
        refresh_token: str,
    ) -> RefreshTokenPyload:
        """Возвращает payload токена обновления в виде dataclass."""
        raise NotImplementedError
