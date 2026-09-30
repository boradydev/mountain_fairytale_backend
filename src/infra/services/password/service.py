from pwdlib import PasswordHash


class PasswordService:
    """Сервис хэширования и проверки паролей."""

    def __init__(self) -> None:
        self._password_hash = PasswordHash.recommended()

    def hash(
        self,
        *,
        password: str,
    ) -> str:
        return self._password_hash.hash(password)

    def verify_password(
        self,
        *,
        plain_password: str,
        hashed_password: str,
    ) -> bool:
        return self._password_hash.verify(
            plain_password,
            hashed_password,
        )
