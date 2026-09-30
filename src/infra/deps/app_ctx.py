from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.infra.services.password.service import PasswordService
from src.infra.services.token.service import JwtTokenService


@dataclass(frozen=True, slots=True)
class AppContext:
    postgres_session_factory: async_sessionmaker[AsyncSession]
    token_service: JwtTokenService
    passwd_service: PasswordService
