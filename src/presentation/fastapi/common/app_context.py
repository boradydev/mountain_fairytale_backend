from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.common.abcs.services.password_service import IPasswordService
from src.presentation.fastapi.common.abcs import ITokenService


@dataclass(frozen=True, slots=True)
class AppContext:
    postgres_session_factory: async_sessionmaker[AsyncSession]
    token_service: ITokenService
    passwd_service: IPasswordService
