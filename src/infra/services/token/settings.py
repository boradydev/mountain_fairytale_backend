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

    @property
    def access_token_expire_seconds(self) -> int:
        return self.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    @property
    def refresh_token_expire_seconds(self) -> int:
        return self.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
