import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse

from src.common.api.schemas import BaseSchema, StdResponse
from src.core.build_info import APP_VERSION
from src.core.paths import PROJECT_DIR


VERSION_PATTERN = re.compile(r"(0|[1-9][0-9]{0,4})\.(0|[1-9][0-9]{0,4})\.(0|[1-9][0-9]{0,4})")


def parse_client_version(value: str) -> tuple[int, ...]:
    if not VERSION_PATTERN.fullmatch(value):
        raise ValueError("Client version must be MAJOR.MINOR.PATCH (components 0..65535)")
    components = tuple(int(component) for component in value.split("."))
    if any(component > 65535 for component in components):
        raise ValueError("Client version components must be 0..65535")
    return components


@dataclass(frozen=True, slots=True)
class ClientCompatibility:
    min_version: str

    def __post_init__(self) -> None:
        parse_client_version(self.min_version)

    @classmethod
    def load(cls, path: Path = PROJECT_DIR / "client_compatibility.toml") -> "ClientCompatibility":
        with path.open("rb") as config_file:
            config = tomllib.load(config_file)
        value = config["flutter"]["min_version"]
        if not isinstance(value, str):
            raise ValueError("flutter.min_version must be a string")
        return cls(min_version=value)


class ClientCompatibilityError(Exception):
    def __init__(self, *, invalid: bool, minimum: str) -> None:
        self.invalid = invalid
        self.minimum = minimum


def require_client_version(
    request: Request,
    x_client_version: Annotated[str | None, Header(description="Installed Flutter MAJOR.MINOR.PATCH")] = None,
) -> None:
    policy: ClientCompatibility = request.app.state.client_compatibility
    try:
        if x_client_version is None:
            raise ValueError("Missing client version")
        version = parse_client_version(x_client_version)
    except ValueError as error:
        raise ClientCompatibilityError(invalid=True, minimum=policy.min_version) from error
    if version < parse_client_version(policy.min_version):
        raise ClientCompatibilityError(invalid=False, minimum=policy.min_version)


async def compatibility_error_handler(_request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ClientCompatibilityError)
    detail = (
        "Не удалось определить версию приложения. Установите актуальную сборку."
        if error.invalid
        else f"Для работы требуется обновить приложение до версии {error.minimum} или новее."
    )
    return JSONResponse(
        status_code=400 if error.invalid else 409,
        headers={"Cache-Control": "no-store"},
        content={
            "code": "CLIENT_VERSION_INVALID" if error.invalid else "CLIENT_UPDATE_REQUIRED",
            "detail": detail,
            "minClientVersion": error.minimum,
            "backendVersion": APP_VERSION,
        },
    )


def install_client_compatibility(app: FastAPI, policy: ClientCompatibility) -> None:
    app.state.client_compatibility = policy
    app.add_exception_handler(ClientCompatibilityError, compatibility_error_handler)


class AppInfo(BaseSchema):
    backend_version: str = APP_VERSION
    min_client_version: str


app_info_router = APIRouter(tags=["Совместимость приложения"])


@app_info_router.get("/app-info", response_model=StdResponse[AppInfo])
async def app_info(request: Request, response: Response) -> StdResponse[AppInfo]:
    response.headers["Cache-Control"] = "no-store"
    policy: ClientCompatibility = request.app.state.client_compatibility
    return StdResponse(data=AppInfo(min_client_version=policy.min_version))
