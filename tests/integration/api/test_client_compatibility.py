from httpx import AsyncClient

from src.common.api.app import fastapi_app
from src.common.api.client_compatibility import ClientCompatibility
from tests.helpers import unique_car_number
from tests.integration.conftest import EmployeeTestData


async def test_required_update_prevents_database_write_and_supported_client_can_retry(
    client: AsyncClient, active_employee: EmployeeTestData, monkeypatch,
) -> None:
    login = await client.post(
        "/public/auth/login",
        json={"username": active_employee.username, "password": active_employee.password},
    )
    assert login.status_code == 200
    client.headers["Authorization"] = f"Bearer {login.json()['data']['accessToken']}"
    monkeypatch.setattr(fastapi_app.state, "client_compatibility", ClientCompatibility("2.0.0"))
    client.headers["X-Client-Version"] = "1.0.0"
    payload = {"model": "Compatibility test", "number": unique_car_number(), "currentMileage": 100.0}
    rejected = await client.post("/protected/cars/create", json=payload)
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "CLIENT_UPDATE_REQUIRED"

    # Read through a supported client to confirm that rejection did not save a car.
    client.headers["X-Client-Version"] = "2.0.0"
    absent = await client.get("/protected/cars/check-duplicate", params={"number": payload["number"]})
    assert absent.status_code == 200
    assert absent.json()["data"] is None

    created = await client.post("/protected/cars/create", json=payload)
    assert created.status_code == 201
    stored = await client.get(f"/protected/cars/{created.json()['data']['carId']}")
    assert stored.status_code == 200
    assert stored.json()["data"]["number"] == payload["number"]
