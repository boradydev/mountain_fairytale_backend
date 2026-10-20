from unittest.mock import AsyncMock

import pytest

from src.common.api.app import fastapi_app
from src.feat.clients.infra.geoapify import Geoapify, get_geoapify
from tests.helpers import delivery_address, unique_phone
from tests.integration.api.test_client_routers import TestClientRouters as ClientAPI


async def test_free_address_and_optional_confirmed_address_persisted(client, active_employee):
    await ClientAPI.login(client, active_employee)
    base = {"name": "Адресный клиент", "phone": unique_phone(), "sleepingThresholdDays": 7}
    legacy = await client.post("/protected/clients/create", json={**base, "address": "Старый адрес"})
    assert legacy.status_code == 201
    assert legacy.json()["data"]["address"] == "Старый адрес"
    assert legacy.json()["data"]["deliveryAddress"] is None
    base["phone"] = unique_phone()
    invalid = delivery_address(confirmed=False)
    response = await client.post("/protected/clients/create", json={**base, "deliveryAddress": invalid})
    assert response.status_code == 422
    address = delivery_address(house="22/5", street="улица Некрасова")
    response = await client.post("/protected/clients/create", json={**base, "deliveryAddress": address})
    assert response.status_code == 201, response.text
    created = response.json()["data"]
    assert created["deliveryAddress"] == address
    assert "22/5" in created["address"]
    fetched = await client.get(f"/protected/clients/{created['clientId']}")
    assert fetched.json()["data"]["deliveryAddress"] == address
    before = fetched.json()["data"]
    assert (
        await client.patch(f"/protected/clients/{created['clientId']}", json={"deliveryAddress": {"house": "23"}})
    ).status_code == 422
    assert (await client.get(f"/protected/clients/{created['clientId']}")).json()["data"] == before


async def test_optimize_draft_returns_permutation_without_saving(client, active_employee):
    await ClientAPI.login(client, active_employee)
    ids = []
    for house in ("147", "148"):
        response = await client.post(
            "/protected/clients/create",
            json={
                "name": "Точка",
                "phone": unique_phone(),
                "sleepingThresholdDays": 7,
                "deliveryAddress": delivery_address(house=house),
            },
        )
        assert response.status_code == 201
        ids.append(response.json()["data"]["clientId"])
    geo = Geoapify()
    geo.optimize = AsyncMock(
        return_value={
            "orderedClientIds": ids[::-1],
            "durationSeconds": 50,
            "distanceMeters": 200,
            "attribution": "test",
        }
    )
    fastapi_app.dependency_overrides[get_geoapify] = lambda: geo
    try:
        response = await client.post("/protected/delivery-route-sheets/optimize-order", json={"orderedClientIds": ids})
        assert response.status_code == 200, response.text
        assert response.json()["data"]["orderedClientIds"] == ids[::-1]
        supplied = geo.optimize.call_args.args[0]
        assert [item[0] for item in supplied] == ids
        assert all(item[1:] == (45.1373445, 41.9974531) for item in supplied)
        assert (
            await client.post(
                "/protected/delivery-route-sheets/optimize-order", json={"orderedClientIds": [ids[0], ids[0]]}
            )
        ).status_code == 422
        for client_id in ids:
            assert (await client.get(f"/protected/clients/{client_id}")).json()["data"]["deliveryAddress"]["confirmed"]
    finally:
        fastapi_app.dependency_overrides.pop(get_geoapify, None)


async def test_location_endpoints_require_authentication(client):
    assert (await client.post("/protected/clients/geocode", json={})).status_code == 401
    assert (await client.get("/protected/locations/tiles/17/1/1")).status_code == 401
    assert (await client.post("/protected/delivery-route-sheets/optimize-order", json={})).status_code == 401


async def test_address_confirmation_lifecycle_and_independent_details(client, active_employee):
    await ClientAPI.login(client, active_employee)
    created = await client.post(
        "/protected/clients/create",
        json={
            "name": "Без карты",
            "phone": unique_phone(),
            "sleepingThresholdDays": 7,
            "address": "  Михайловск, заезд Добрый, 17  ",
            "deliveryDetails": "Вход со двора",
        },
    )
    assert created.status_code == 201, created.text
    data = created.json()["data"]
    path = f"/protected/clients/{data['clientId']}"
    assert data["address"] == "Михайловск, заезд Добрый, 17"
    assert data["deliveryAddress"] is None
    assert (await client.get(path)).json()["data"]["deliveryDetails"] == "Вход со двора"
    confirmed = await client.patch(path, json={"deliveryAddress": delivery_address()})
    assert confirmed.status_code == 200, confirmed.text
    canonical = confirmed.json()["data"]["address"]
    details = await client.patch(path, json={"deliveryDetails": "Вторые ворота"})
    assert details.json()["data"]["deliveryAddress"]["confirmed"] is True
    unchanged = await client.patch(path, json={"address": canonical})
    assert unchanged.json()["data"]["deliveryAddress"]["confirmed"] is True
    changed = await client.patch(path, json={"address": "Другой адрес, дом 12"})
    assert changed.status_code == 200, changed.text
    fetched = (await client.get(path)).json()["data"]
    assert fetched["deliveryAddress"] is None
    assert fetched["address"] == "Другой адрес, дом 12"
    assert fetched["deliveryDetails"] == "Вторые ворота"
    assert (await client.patch(path, json={"deliveryAddress": delivery_address()})).status_code == 200
    cleared = await client.patch(path, json={"deliveryAddress": None})
    assert cleared.status_code == 200
    assert (await client.get(path)).json()["data"]["deliveryAddress"] is None
    for body in ({"address": " "}, {"address": None}, {"deliveryDetails": None}):
        assert (await client.patch(path, json=body)).status_code == 422


async def test_all_unconfirmed_clients_reported_before_any_provider_request(client, active_employee):
    await ClientAPI.login(client, active_employee)
    ids = []
    for name in ("Первый без координат", "Второй без координат"):
        response = await client.post(
            "/protected/clients/create",
            json={
                "name": name,
                "phone": unique_phone(),
                "sleepingThresholdDays": 7,
                "address": "Ставрополь, произвольный адрес",
            },
        )
        assert response.status_code == 201, response.text
        ids.append(response.json()["data"]["clientId"])
    geo = Geoapify()
    geo.optimize = AsyncMock()
    fastapi_app.dependency_overrides[get_geoapify] = lambda: geo
    try:
        response = await client.post("/protected/delivery-route-sheets/optimize-order", json={"orderedClientIds": ids})
        assert response.status_code == 422, response.text
        assert [item["clientId"] for item in response.json()["clients"]] == ids
        assert "Первый без координат" in response.json()["detail"]
        assert "Второй без координат" in response.json()["detail"]
        geo.optimize.assert_not_awaited()
    finally:
        fastapi_app.dependency_overrides.pop(get_geoapify, None)


@pytest.mark.parametrize("job_ids", [["a"], ["a", "a"], ["a", "foreign"]])
async def test_provider_partial_or_duplicate_result_is_rejected(job_ids):
    from src.feat.clients.domain.location_excs import InvalidGeoResponse

    geo = Geoapify()
    geo._json = AsyncMock(
        return_value={
            "features": [
                {
                    "properties": {
                        "time": 10,
                        "distance": 100,
                        "waypoints": [
                            {"original_location": geo.depot, "actions": [{"type": "start"}]},
                            {
                                "original_location": geo.depot,
                                "actions": [
                                    *[{"type": "job", "job_id": value} for value in job_ids],
                                    {"type": "end"},
                                ],
                            },
                        ],
                    }
                }
            ]
        }
    )
    with pytest.raises(InvalidGeoResponse):
        await geo.optimize([("a", 45.1, 42.0), ("b", 45.2, 42.1)])


def test_geocoding_filters_wrong_region_locality_and_district():
    from src.feat.clients.api.address_schemas import AddressSearchReq

    address = AddressSearchReq(district="Шпаковский округ", locality="г. Михайловск", street="Добрый заезд", house="17")
    base = {
        "country_code": "ru",
        "state": "Ставропольский край",
        "city": "Михайловск",
        "county": "Шпаковский муниципальный округ",
        "formatted": "Добрый заезд 17, Михайловск",
        "lat": 45.1538489,
        "lon": 42.0564513,
        "result_type": "building",
        "housenumber": "17",
        "rank": {"confidence": 1, "confidence_street_level": 1},
    }
    data = {
        "features": [
            {"properties": {**base, **override}}
            for override in [
                {},
                {"state": "Свердловская область"},
                {"city": "Ставрополь"},
                {"county": "Другой округ"},
            ]
        ]
    }
    candidates = Geoapify._candidates(data, address)
    assert len(candidates) == 1
    assert candidates[0].exact_house is True
    assert candidates[0].latitude == 45.1538489


@pytest.mark.parametrize(
    "override",
    [
        {"latitude": float("nan")},
        {"longitude": 90},
        {"confirmed": False},
        {"house": "   "},
    ],
)
def test_invalid_delivery_location_is_rejected(override):
    from pydantic import ValidationError

    from src.feat.clients.api.address_schemas import DeliveryAddress

    with pytest.raises(ValidationError):
        DeliveryAddress.model_validate(delivery_address(**override))


async def test_stavropol_address_can_be_saved_without_district(client, active_employee):
    await ClientAPI.login(client, active_employee)
    address = delivery_address(locality="г. Ставрополь", street="улица Ленина", house="120")
    address.pop("district")
    response = await client.post(
        "/protected/clients/create",
        json={
            "name": "Клиент без района",
            "phone": unique_phone(),
            "sleepingThresholdDays": 7,
            "deliveryAddress": address,
        },
    )
    assert response.status_code == 201, response.text
    created = response.json()["data"]
    assert created["address"] == "Ставропольский край, г. Ставрополь, улица Ленина, 120"
    assert created["deliveryAddress"]["district"] == ""
    fetched = await client.get(f"/protected/clients/{created['clientId']}")
    assert fetched.json()["data"]["deliveryAddress"] == {**address, "district": ""}


async def test_search_without_district_does_not_send_county_filter():
    from src.feat.clients.api.address_schemas import AddressSearchReq

    geo = Geoapify()
    geo._json = AsyncMock(
        return_value={
            "features": [
                {
                    "properties": {
                        "country_code": "ru",
                        "state": "Ставропольский край",
                        "city": "Ставрополь",
                        "county": "городской округ Ставрополь",
                        "formatted": "Ленина 120, Ставрополь",
                        "lat": 45.0413802,
                        "lon": 41.989106,
                        "result_type": "building",
                        "housenumber": "120",
                        "rank": {"confidence": 1, "confidence_street_level": 1},
                    }
                }
            ]
        }
    )
    result = await geo.search(AddressSearchReq(locality="г. Ставрополь", street="улица Ленина", house="120"))
    assert len(result.candidates) == 1
    assert result.candidates[0].exact_house
    assert "county" not in geo._json.call_args.args[1]
    assert geo._json.await_count == 1
