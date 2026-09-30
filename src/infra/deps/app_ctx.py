from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass(frozen=True, slots=True)
class AppContext:
    postgres_session_factory: async_sessionmaker[AsyncSession]
    token_service: None
    passwd_service: None
