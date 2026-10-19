import asyncio
import json
import os
import re
import threading
import time
from collections import OrderedDict
from functools import lru_cache
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.feat.clients.api.address_schemas import AddressCandidate, AddressSearchReq, AddressSearchResp
from src.feat.clients.domain.location_excs import GeoQuotaExceeded, GeoUnavailable, InvalidGeoResponse


class _Action(BaseModel):
    type: str
    job_id: str | None = None


class _Waypoint(BaseModel):
    original_location: list[float]
    actions: list[_Action]


class _PlanProperties(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    time: float = Field(ge=0)
    distance: float = Field(ge=0)
    waypoints: list[_Waypoint]


class _Feature(BaseModel):
    properties: _PlanProperties


class _Plan(BaseModel):
    features: list[_Feature] = Field(min_length=1, max_length=1)


class Geoapify:
    depot = [41.9974531, 45.1373445]
    attribution = "Powered by Geoapify; © OpenStreetMap contributors"

    def __init__(self) -> None:
        self._lock = asyncio.Semaphore(4)
        self._request_lock = threading.Lock()
        self._last_request = 0.0
        self._tiles: OrderedDict[tuple[int, int, int], bytes] = OrderedDict()

    def _request(self, path: str, params: dict[str, str], body: object = None, *, maps: bool = False) -> bytes:
        key = os.environ.get("GEOAPIFY_API_KEY", "")
        if not key:
            raise GeoUnavailable
        host = "maps.geoapify.com" if maps else "api.geoapify.com"
        url = f"https://{host}/v1/{path}?{urlencode({**params, 'apiKey': key})}"
        request = Request(
            url,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "MountainFairytale/1.0"},
        )
        try:
            with self._request_lock:
                time.sleep(max(0, 0.22 - (time.monotonic() - self._last_request)))
                self._last_request = time.monotonic()
            with urlopen(request, timeout=10) as response:
                data = response.read(8_000_001)
                if len(data) > 8_000_000:
                    raise InvalidGeoResponse
                return data
        except HTTPError as exc:
            if exc.code == 429:
                raise GeoQuotaExceeded from None
            raise GeoUnavailable from None
        except (URLError, TimeoutError, OSError):
            # Never expose provider URLs: they contain the secret apiKey.
            raise GeoUnavailable from None

    async def _json(self, path: str, params: dict[str, str], body: object = None) -> dict[str, Any]:
        async with self._lock:
            data = await asyncio.to_thread(self._request, path, params, body)
        try:
            result = json.loads(data)
            if not isinstance(result, dict):
                raise InvalidGeoResponse
            return result
        except (ValueError, TypeError):
            raise InvalidGeoResponse from None

    async def search(self, address: AddressSearchReq) -> AddressSearchResp:
        params = {
            "country": "Россия",
            "state": "Ставропольский край",
            "city": re.sub(r"^(г\.?|с\.?|п\.?|х\.?|ст-ца)\s+", "", address.locality, flags=re.IGNORECASE),
            "county": address.district,
            "street": address.street,
            "housenumber": address.house,
            "filter": "countrycode:ru",
            "lang": "ru",
            "limit": "5",
        }
        data = await self._json("geocode/search", params)
        candidates = self._candidates(data, address)
        if not any(c.exact_house for c in candidates):
            data = await self._json(
                "geocode/search",
                {"text": "Россия, " + address.formatted, "filter": "countrycode:ru", "lang": "ru", "limit": "5"},
            )
            candidates = self._candidates(data, address) or candidates
        return AddressSearchResp(candidates=candidates)

    @staticmethod
    def _candidates(data: dict[str, Any], address: AddressSearchReq) -> list[AddressCandidate]:
        result = []

        def normalized(value: str) -> str:
            value = value.casefold().replace("ё", "е")
            value = re.sub(
                r"\b(г|с|п|ст|ст-ца|город|село|посёлок|поселок|станица|хутор|х|район|муниципальный|городской|округ)\b",
                " ",
                value,
            )
            return " ".join(re.findall(r"[а-яa-z0-9]+", value))

        try:
            for feature in data.get("features", []):
                p = feature["properties"]
                if p.get("country_code") != "ru" or p.get("state") != "Ставропольский край":
                    continue
                locality = p.get("city") or p.get("town") or p.get("village") or ""
                if normalized(locality) != normalized(address.locality):
                    continue
                county = p.get("county", "")
                if county and normalized(county) != normalized(address.district):
                    continue
                result.append(
                    AddressCandidate(
                        formatted=p["formatted"],
                        latitude=p["lat"],
                        longitude=p["lon"],
                        confidence=p.get("rank", {}).get("confidence", 0),
                        exact_house=p.get("result_type") == "building"
                        and str(p.get("housenumber", "")).casefold() == address.house.casefold()
                        and p.get("rank", {}).get("confidence_street_level", 0) == 1,
                    )
                )
        except (KeyError, TypeError, ValueError, AttributeError):
            raise InvalidGeoResponse from None
        return result

    async def optimize(self, locations: list[tuple[str, float, float]]) -> dict[str, Any]:
        ids = [item[0] for item in locations]
        body = {
            "mode": "drive",
            "type": "balanced",
            "traffic": "free_flow",
            "agents": [{"start_location": self.depot, "end_location": self.depot}],
            "jobs": [{"id": i, "location": [lon, lat], "duration": 0} for i, lat, lon in locations],
        }
        data = await self._json("routeplanner", {}, body)
        try:
            props = _Plan.model_validate(data).features[0].properties
            actions = [a for w in props.waypoints for a in w.actions]
            ordered = [a.job_id for a in actions if a.type == "job"]
            if (
                len(ordered) != len(ids)
                or set(ordered) != set(ids)
                or not actions
                or actions[0].type != "start"
                or actions[-1].type != "end"
                or props.waypoints[0].original_location != self.depot
                or props.waypoints[-1].original_location != self.depot
            ):
                raise InvalidGeoResponse
        except (ValidationError, IndexError, TypeError):
            raise InvalidGeoResponse from None
        return {
            "orderedClientIds": ordered,
            "durationSeconds": props.time,
            "distanceMeters": props.distance,
            "attribution": self.attribution,
            "trafficModel": "free_flow",
        }

    async def tile(self, z: int, x: int, y: int) -> bytes:
        if not 8 <= z <= 19 or not 0 <= x < 2**z or not 0 <= y < 2**z:
            raise InvalidGeoResponse
        key = (z, x, y)
        async with self._lock:
            if key in self._tiles:
                self._tiles.move_to_end(key)
                return self._tiles[key]
            data = await asyncio.to_thread(self._request, f"tile/osm-carto/{z}/{x}/{y}.png", {}, maps=True)
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise InvalidGeoResponse
            self._tiles[key] = data
            if len(self._tiles) > 512:
                self._tiles.popitem(last=False)
            return data


@lru_cache(maxsize=1)
def get_geoapify() -> Geoapify:
    return Geoapify()
