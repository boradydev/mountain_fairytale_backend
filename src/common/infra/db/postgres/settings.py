from dataclasses import dataclass, field
from os import environ


@dataclass(frozen=True, slots=True, kw_only=True)
class PostgresSettings:
    POSTGRES_HOST: str = field(default_factory=lambda: environ["POSTGRES_HOST"])
    POSTGRES_PORT: str = field(default_factory=lambda: environ["POSTGRES_PORT"])
    POSTGRES_USER: str = field(default_factory=lambda: environ["POSTGRES_USER"])
    POSTGRES_PASSWORD: str = field(default_factory=lambda: environ["POSTGRES_PASSWORD"])
    POSTGRES_DB: str = field(default_factory=lambda: environ["POSTGRES_DB"])

    @property
    def DB_URL_ASYNC(self):
        return (
            f"postgresql+asyncpg://"
            f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/"
            f"{self.POSTGRES_DB}"
        )

    @property
    def DB_URL_SYNC(self):
        return (
            f"postgresql+psycopg://"
            f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/"
            f"{self.POSTGRES_DB}"
        )
