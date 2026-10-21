from typing import Any, Protocol
from uuid import UUID

from src.feat.clients.app.abcs.client_uow_abcs import IClientsUOW
from src.feat.clients.domain.location_excs import MissingClientLocation


class RouteOptimizer(Protocol):
    async def optimize(self, locations: list[tuple[str, float, float]]) -> dict[str, Any]: ...


class OptimizeRouteUseCase:
    def __init__(self, uow: IClientsUOW, geo: RouteOptimizer) -> None:
        self._uow = uow
        self._geo = geo

    async def execute(self, ids: list[UUID]) -> dict[str, Any]:
        locations = []
        missing: list[dict[str, str]] = []
        async with self._uow as uow:
            for client_id in ids:
                client = await uow.clients.get_by_id(client_id)
                if client is None or not client.delivery_address or not client.delivery_address.get("confirmed"):
                    missing.append({"clientId": str(client_id), "name": client.name if client else str(client_id)})
                    continue
                a = client.delivery_address
                locations.append((str(client_id), a["latitude"], a["longitude"]))
        if missing:
            raise MissingClientLocation(missing)
        return await self._geo.optimize(locations)
