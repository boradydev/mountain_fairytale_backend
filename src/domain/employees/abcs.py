from abc import ABC, abstractmethod


class IPasswordService(ABC):
    """Интерфейс для безопасной работы с паролями пользователей."""

    @abstractmethod
    def hash(
        self,
        *,
        password: str,
    ) -> str:
        """Преобразует сырой пароль в безопасный хеш."""

    @abstractmethod
    def verify_password(
        self,
        *,
        plain_password: str,
        hashed_password: str,
    ) -> bool:
        """Проверяет соответствие сырого пароля ранее созданному хешу."""
