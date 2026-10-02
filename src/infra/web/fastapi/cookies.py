from abc import ABC
from typing import Literal

from fastapi import Request, Response

from src.infra.services.token.settings import JwtSettings
from src.infra.web.fastapi.excs import CookieNotFound
from src.presentation.fastapi.auth.abcs.cookies import IAuthCookieManager


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
        )


class AuthCookieManager(IFastapiCookieManager, IAuthCookieManager):
    _ACCESS_TOKEN = "access_token"
    _REFRESH_TOKEN = "refresh_token"

    def __init__(
        self,
        request: Request,
        response: Response,
        settings: JwtSettings,
        httponly: bool = True,
        secure: bool = True,
        same_site: Literal["lax", "strict", "none"] = "lax",
    ):
        self._request = request
        self._response = response
        self._httponly = httponly
        self.settings = settings
        self._secure = secure
        self._same_site: Literal["lax", "strict", "none"] = same_site

    def set_auth_cookies(
        self,
        *,
        access_token: str,
        refresh_token: str,
    ) -> None:
        self._set(
            key=self._ACCESS_TOKEN,
            value=access_token,
            max_age=self.settings.access_token_expire_seconds,
        )
        self._set(
            key=self._REFRESH_TOKEN,
            value=refresh_token,
            max_age=self.settings.refresh_token_expire_seconds,
        )

    def delete_auth_cookies(self) -> None:
        self._response.delete_cookie(key=self._ACCESS_TOKEN)
        self._response.delete_cookie(key=self._REFRESH_TOKEN)

    def _get(self, key: str) -> str:
        cookie = self._request.cookies.get(key)
        if not cookie:
            raise CookieNotFound
        return cookie

    @property
    def access_token(self) -> str:
        return self._get(self._ACCESS_TOKEN)

    @property
    def refresh_token(self) -> str:
        return self._get(self._REFRESH_TOKEN)
