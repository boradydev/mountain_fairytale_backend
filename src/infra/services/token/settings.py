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
