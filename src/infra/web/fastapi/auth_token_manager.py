from abc import ABC
from typing import Literal

from fastapi import Request, Response

from src.infra.services.token.settings import JwtSettings
from src.feat.auth.api.abcs.auth_token_manager_abcs import IAuthTokenManager


class IFastapiCookieManager(ABC):
    _response: Response
    _httponly: bool
    _secure: bool
    _same_site: Literal["lax", "strict", "none"]

    def _set(
        self,
        key: str,
        value: str,
        max_age: int | None = None,
    ) -> None:
        self._response.set_cookie(
            key=key,
            value=value,
            httponly=self._httponly,
            secure=self._secure,
            max_age=max_age,
            samesite=self._same_site,
            path="/",
        )


class AuthTokenManager(IFastapiCookieManager, IAuthTokenManager):
    _ACCESS_KEY = "access-token"
    _REFRESH_KEY = "refresh-token"

    def __init__(
        self,
        request: Request,
        response: Response,
        settings: JwtSettings,
        httponly: bool = True,
        secure: bool = False,
        same_site: Literal["lax", "strict", "none"] = "lax",
    ) -> None:
        self._request = request
        self._response = response
        self._httponly = httponly
        self._secure = secure
        self._same_site = same_site
        self.settings = settings

    # --- Управление куками (для Web) ---

    def set_auth_cookies(
        self,
        *,
        access_token: str,
        refresh_token: str,
    ) -> None:
        self._set(
            key=self._ACCESS_KEY,
            value=access_token,
            max_age=self.settings.ACCESS_TOKEN_EXPIRE_SECONDS,
        )
        self._set(
            key=self._REFRESH_KEY,
            value=refresh_token,
            max_age=self.settings.REFRESH_TOKEN_EXPIRE_SECONDS,
        )

    def delete_auth_cookies(self) -> None:
        self._response.delete_cookie(
            key=self._ACCESS_KEY,
            path="/",
        )
        self._response.delete_cookie(
            key=self._REFRESH_KEY,
            path="/",
        )

    # --- Извлечение из COOKIES ---

    @property
    def access_token_from_cookie(self) -> str | None:
        return self._request.cookies.get(self._ACCESS_KEY)

    @property
    def refresh_token_from_cookie(self) -> str | None:
        return self._request.cookies.get(self._REFRESH_KEY)

    # --- Извлечение из HEADERS (для Flutter) ---

    @property
    def access_token_from_header(self) -> str | None:
        """Извлекает токен из стандартного заголовка Authorization: Bearer <token>."""
        auth_header = self._request.headers.get("Authorization")
        if not auth_header:
            return None

        # Ожидаем формат "Bearer <token>"
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]

        return None
