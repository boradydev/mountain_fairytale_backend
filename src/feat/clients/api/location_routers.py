import base64
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path
from pydantic import ConfigDict, Field, model_validator

from src.common.api.deps import Context
from src.common.api.excs_handlers import map_exceptions_to_responses
from src.common.api.schemas import BaseSchema, StdResponse
from src.feat.clients.api.address_schemas import AddressSearchReq, AddressSearchResp
from src.feat.clients.domain.location_excs import (
    GeoQuotaExceeded,
    GeoUnavailable,
    InvalidGeoResponse,
    MissingClientLocation,
)
from src.feat.clients.infra.geoapify import Geoapify, get_geoapify


location_router = APIRouter(tags=["Адреса и оптимизация"])
GeoDep = Annotated[Geoapify, Depends(get_geoapify)]


class OptimizeReq(BaseSchema):
    model_config = ConfigDict(extra="forbid")
    ordered_client_ids: list[UUID] = Field(min_length=2, max_length=30)

    @model_validator(mode="after")
    def unique_ids(self):
        if len(set(self.ordered_client_ids)) != len(self.ordered_client_ids):
            raise ValueError("Client IDs must be unique")
        return self


@location_router.post(
    "/clients/geocode",
    response_model=StdResponse[AddressSearchResp],
    responses=map_exceptions_to_responses(GeoUnavailable, GeoQuotaExceeded, InvalidGeoResponse),
    description="Поиск здания в Ставропольском крае. Не сохраняет клиента и не подтверждает координаты.",
)
async def geocode_address(body: AddressSearchReq, geo: GeoDep):
    return StdResponse(data=await geo.search(body))


@location_router.get(
    "/locations/tiles/{z}/{x}/{y}",
    responses=map_exceptions_to_responses(GeoUnavailable, GeoQuotaExceeded, InvalidGeoResponse),
    description="Защищённая загрузка PNG-тайла карты как base64. Ключ провайдера остаётся на сервере.",
)
async def map_tile(z: Annotated[int, Path(ge=8, le=19)], x: int, y: int, geo: GeoDep):
    return StdResponse(data={"png": base64.b64encode(await geo.tile(z, x, y)).decode()})


@location_router.post(
    "/delivery-route-sheets/optimize-order",
    responses=map_exceptions_to_responses(GeoUnavailable, GeoQuotaExceeded, InvalidGeoResponse, MissingClientLocation),
    description="Рекомендуемый порядок 2–30 клиентов. Старт и финиш — склад. Документ не сохраняется.",
)
async def optimize_order(body: OptimizeReq, ctx: Context, geo: GeoDep):
    use_case = ctx.clients_use_cases.optimize_route(geo)
    return StdResponse(data=await use_case.execute(body.ordered_client_ids))
