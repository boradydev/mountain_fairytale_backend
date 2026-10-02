from abc import ABC, abstractmethod


class IAuthCookieManager(ABC):
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
    def access_token(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def refresh_token(self) -> str:
        raise NotImplementedError
