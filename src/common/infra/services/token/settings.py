from dataclasses import dataclass, field
from os import environ


@dataclass(frozen=True, slots=True, kw_only=True)
class JwtSettings:
    JWT_SECRET_KEY: str = field(default_factory=lambda: environ["JWT_SECRET_KEY"])
    JWT_ALGORITHM: str = field(default_factory=lambda: environ["JWT_ALGORITHM"])

    ACCESS_TOKEN_EXPIRE_MINUTES: int = field(
        default_factory=lambda: int(environ["ACCESS_TOKEN_EXPIRE_MINUTES"])
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = field(
        default_factory=lambda: int(environ["REFRESH_TOKEN_EXPIRE_DAYS"])
    )

    # Делаем поля доступными в init, но по умолчанию ставим None
    ACCESS_TOKEN_EXPIRE_SECONDS: int | None = None
    REFRESH_TOKEN_EXPIRE_SECONDS: int | None = None

    def __post_init__(self) -> None:
        # Если секунды для access-токена не переданы, высчитываем их из минут
        if self.ACCESS_TOKEN_EXPIRE_SECONDS is None:
            seconds = self.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            object.__setattr__(self, "ACCESS_TOKEN_EXPIRE_SECONDS", seconds)

        # Если секунды для refresh-токена не переданы, высчитываем их из дней
        if self.REFRESH_TOKEN_EXPIRE_SECONDS is None:
            seconds = self.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
            object.__setattr__(self, "REFRESH_TOKEN_EXPIRE_SECONDS", seconds)
