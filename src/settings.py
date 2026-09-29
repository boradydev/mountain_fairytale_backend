from dataclasses import dataclass, field
from os import environ


@dataclass(frozen=True, slots=True, kw_only=True)
class UvicornSettings:
    APP_HOST: str = field(default_factory=lambda: environ["APP_HOST"])
    APP_PORT: int = field(default_factory=lambda: int(environ["APP_PORT"]))
    FASTAPI_APP: str = "src.presentation.fastapi.app:fastapi_app"
