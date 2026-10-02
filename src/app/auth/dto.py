from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthTokensDTO:
    access_token: str
    refresh_token: str
