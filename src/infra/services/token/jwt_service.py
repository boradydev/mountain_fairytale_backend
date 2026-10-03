from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import InvalidTokenError

from src.infra.services.token.excs import (
    InvalidAccessTokenException,
    InvalidRefreshTokenException,
)
from src.infra.services.token.settings import JwtSettings
from src.api.fastapi.common.abcs import ITokenService
from src.api.fastapi.auth.auth_schemas import AccessTokenPyload, RefreshTokenPyload


class JwtTokenService(ITokenService):
    """Сервис создания и проверки JWT токенов."""

    def __init__(
        self,
        settings: JwtSettings | None = None,
    ) -> None:
        self._settings = settings or JwtSettings()

    def create_access_token(
        self,
        **payload: Any,
    ) -> str:
        expires_at = self._get_access_token_expiration()

        return self._encode(
            payload={
                **payload,
                "token_type": "access",
            },
            expires_at=expires_at,
        )

    def get_payload_access_token(
        self,
        access_token: str,
    ) -> AccessTokenPyload:
        try:
            payload = self._decode(access_token)
        except InvalidTokenError as exc:
            raise InvalidAccessTokenException from exc

        return AccessTokenPyload.model_validate(payload)

    def create_refresh_token(
        self,
        **payload: Any,
    ) -> str:
        expires_at = self._get_refresh_token_expiration()

        return self._encode(
            payload={
                **payload,
                "token_type": "refresh",
            },
            expires_at=expires_at,
        )

    def get_payload_refresh_token(
        self,
        refresh_token: str,
    ) -> RefreshTokenPyload:
        try:
            payload = self._decode(refresh_token)
        except InvalidTokenError as exc:
            raise InvalidRefreshTokenException from exc

        return RefreshTokenPyload.model_validate(payload)

    def _get_access_token_expiration(self) -> datetime:
        return datetime.now(UTC) + timedelta(
            seconds=self._settings.ACCESS_TOKEN_EXPIRE_SECONDS,
        )

    def _get_refresh_token_expiration(self) -> datetime:
        return datetime.now(UTC) + timedelta(
            seconds=self._settings.REFRESH_TOKEN_EXPIRE_SECONDS,
        )

    def _encode(
        self,
        *,
        payload: dict[str, Any],
        expires_at: datetime,
    ) -> str:
        payload = {
            **payload,
            "exp": expires_at,
        }

        return jwt.encode(
            payload,
            self._settings.JWT_SECRET_KEY,
            algorithm=self._settings.JWT_ALGORITHM,
        )

    def _decode(
        self,
        token: str,
    ) -> dict[str, Any]:
        payload = jwt.decode(
            token,
            self._settings.JWT_SECRET_KEY,
            algorithms=[self._settings.JWT_ALGORITHM],
        )

        return payload
