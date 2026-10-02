from abc import ABC, abstractmethod


class IAuthTokenManager(ABC):
    @abstractmethod
    def set_auth_cookies(
        self,
        *,
        access_token: str,
        refresh_token: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_auth_cookies(self) -> None:
        raise NotImplementedError

    @property
    @abstractmethod
    def access_token_from_cookie(self) -> str | None:
        raise NotImplementedError

    @property
    @abstractmethod
    def refresh_token_from_cookie(self) -> str | None:
        raise NotImplementedError

    @property
    @abstractmethod
    def access_token_from_header(self) -> str | None:
        raise NotImplementedError
