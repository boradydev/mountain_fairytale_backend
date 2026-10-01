from dataclasses import dataclass, field
from os import environ


@dataclass(frozen=True, slots=True, kw_only=True)
class AdminSettings:
    ADMIN_USERNAME: str = field(default_factory=lambda: environ["ADMIN_USERNAME"])
    ADMIN_PASSWORD: str = field(default_factory=lambda: environ["ADMIN_PASSWORD"])
