"""Supply current document versions in tests of unrelated API behavior."""

import re
from typing import Any

from httpx import AsyncClient, Response

from src.core.uuid7 import uuid7
from tests.helpers import unique_car_number


async def patch_with_revision(client: AsyncClient, url: str, **kwargs: Any) -> Response:
    body = kwargs.get("json")
    if re.fullmatch(r"/protected/(delivery-route-sheets|pickup-sheets)/[^/]+", url) and body:
        if "expectedRevision" not in body:
            response = await client.get(url)
            revision = response.json()["data"]["revision"] if response.status_code == 200 else 1
            kwargs["json"] = {**body, "expectedRevision": revision}
    return await client.patch(url, **kwargs)


async def create_delivery(client: AsyncClient, *, json: dict[str, Any]) -> Response:
    """Create customer-bound sales as delivery documents with valid resources."""
    driver = await client.post("/protected/drivers/create", json={"name": f"Driver {uuid7()}"})
    car = await client.post("/protected/cars/create", json={"model": "Test", "number": unique_car_number()})
    assert driver.status_code == car.status_code == 201
    return await client.post(
        "/protected/delivery-route-sheets/create",
        json={
            **json,
            "driverId": driver.json()["data"]["driverId"],
            "carId": car.json()["data"]["carId"],
            "startMileage": 0,
        },
    )
