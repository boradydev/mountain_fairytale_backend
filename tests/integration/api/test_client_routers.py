from uuid import uuid4

import pytest
from httpx import AsyncClient

from src.core.uuid7 import uuid7
from tests.helpers import delivery_address
from tests.integration.conftest import EmployeeTestData


BASE_PATH = "/protected/clients"


class TestClientRouters:
    @staticmethod
    async def login(client: AsyncClient, employee: EmployeeTestData) -> None:
        response = await client.post(
            "/public/auth/login",
            json={"username": employee.username, "password": employee.password},
        )
        assert response.status_code == 200

    @staticmethod
    def payload(**overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "name": f"Client {uuid7()}",
            "phone": uuid4().hex,
            "deliveryAddress": delivery_address(),
            "sleepingThresholdDays": 30,
        }
        address = overrides.get("address")
        if isinstance(address, str) and 0 < len(address) <= 500:
            overrides = dict(overrides)
            overrides.pop("address")
            payload["deliveryAddress"] = delivery_address(street=address)
        payload.update(overrides)
        return payload

    async def test_create_get_update_and_duplicate_phone(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)
        first_payload = self.payload()
        first_response = await client.post(f"{BASE_PATH}/create", json=first_payload)
        assert first_response.status_code == 201

        first = first_response.json()["data"]
        assert first["clientId"]
        assert first["isActive"] is True
        assert first["lastDeliveryDate"] is None
        assert first["lastDeliveryQuantity"] is None

        get_response = await client.get(f"{BASE_PATH}/{first['clientId']}")
        assert get_response.status_code == 200
        assert get_response.json()["data"]["phone"] == first_payload["phone"]

        duplicate = await client.post(
            f"{BASE_PATH}/create",
            json=self.payload(phone=first_payload["phone"]),
        )
        assert duplicate.status_code == 409

        second_response = await client.post(
            f"{BASE_PATH}/create",
            json=self.payload(),
        )
        assert second_response.status_code == 201
        second = second_response.json()["data"]

        conflict = await client.patch(
            f"{BASE_PATH}/{second['clientId']}",
            json={"phone": first_payload["phone"]},
        )
        assert conflict.status_code == 409
        after_conflict = await client.get(f"{BASE_PATH}/{second['clientId']}")
        assert after_conflict.json()["data"]["phone"] == second["phone"]

        update = await client.patch(
            f"{BASE_PATH}/{first['clientId']}",
            json={
                "name": "Updated client",
                "cooldownUntil": None,
                "isActive": False,
            },
        )
        assert update.status_code == 200
        assert update.json()["data"]["name"] == "Updated client"
        assert update.json()["data"]["isActive"] is False

        reactivate = await client.patch(
            f"{BASE_PATH}/{first['clientId']}",
            json={"isActive": True},
        )
        assert reactivate.status_code == 200
        assert reactivate.json()["data"]["isActive"] is True

        assert (await client.patch(f"{BASE_PATH}/{first['clientId']}", json={})).status_code == 422

    async def test_list_pagination_and_deactivated_record(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        initial_active_response = await client.get(BASE_PATH)
        assert initial_active_response.status_code == 200
        initial_active_total = initial_active_response.json()["total"]

        initial_all_response = await client.get(
            BASE_PATH,
            params={"include_deactivated": True, "offset": 0, "limit": 1},
        )
        assert initial_all_response.status_code == 200
        initial_all_total = initial_all_response.json()["total"]

        created = []
        for _index in range(3):
            response = await client.post(
                f"{BASE_PATH}/create",
                json=self.payload(name=f"Pagination client {uuid7()}"),
            )
            assert response.status_code == 201
            created.append(response.json()["data"])

        inactive = created[0]
        await client.patch(
            f"{BASE_PATH}/{inactive['clientId']}",
            json={"isActive": False},
        )

        active_page = await client.get(
            BASE_PATH,
            params={"include_deactivated": False, "offset": 0, "limit": 1},
        )
        assert active_page.status_code == 200
        active_data = active_page.json()
        assert active_data["total"] == initial_active_total + 2
        assert active_data["limit"] == 1
        assert len(active_data["data"]["clients"]) == 1

        all_clients = await client.get(
            BASE_PATH,
            params={"include_deactivated": True, "offset": 0, "limit": 10},
        )
        assert all_clients.status_code == 200
        all_data = all_clients.json()
        assert all_data["total"] == initial_all_total + 3
        assert len(all_data["data"]["clients"]) == min(initial_all_total + 3, 10)

        inactive_get = await client.get(f"{BASE_PATH}/{inactive['clientId']}")
        assert inactive_get.status_code == 200
        assert inactive_get.json()["data"]["isActive"] is False

    async def test_check_duplicate_requires_all_fields_and_returns_data_or_null(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)
        created_response = await client.post(
            f"{BASE_PATH}/create",
            json=self.payload(),
        )
        assert created_response.status_code == 201
        created = created_response.json()["data"]

        for missing in ("name", "phone", "address"):
            params = {
                "name": created["name"],
                "phone": created["phone"],
                "address": created["address"],
            }
            params.pop(missing)
            response = await client.get(f"{BASE_PATH}/check-duplicate", params=params)
            assert response.status_code == 422

        exact = await client.get(
            f"{BASE_PATH}/check-duplicate",
            params={
                "name": created["name"],
                "phone": created["phone"],
                "address": created["address"],
            },
        )
        assert exact.status_code == 200
        assert exact.json()["data"]["clientId"] == created["clientId"]

        none = await client.get(
            f"{BASE_PATH}/check-duplicate",
            params={
                "name": "Unrelated name",
                "phone": uuid4().hex,
                "address": "Unrelated address",
            },
        )
        assert none.status_code == 200
        assert none.json()["data"] is None

        await client.patch(
            f"{BASE_PATH}/{created['clientId']}",
            json={"isActive": False},
        )
        inactive_match = await client.get(
            f"{BASE_PATH}/check-duplicate",
            params={
                "name": created["name"],
                "phone": created["phone"],
                "address": created["address"],
            },
        )
        assert inactive_match.status_code == 200
        assert inactive_match.json()["data"]["clientId"] == created["clientId"]

    async def test_invalid_related_ids_and_unauthorized(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)
        invalid_reference = await client.post(
            f"{BASE_PATH}/create",
            json=self.payload(salesRepresentativeId=str(uuid7())),
        )
        assert invalid_reference.status_code == 422

        assert (await client.post(f"{BASE_PATH}/create", json=self.payload())).status_code == 201

    async def test_unauthorized_access(self, client: AsyncClient) -> None:
        response = await client.get(BASE_PATH)
        assert response.status_code == 401

    async def test_search_filters_before_pagination_and_normalizes_phone(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)
        marker = uuid4().hex
        rows = []
        for index in range(3):
            response = await client.post(
                f"{BASE_PATH}/create",
                json=self.payload(
                    name=f"Магазин {marker} {index}",
                    address=f"Москва, улица {marker}, {index}",
                    phone=f"+7 (912) 345-67-{index:02d}",
                ),
            )
            assert response.status_code == 201
            rows.append(response.json()["data"])
        for query in (f"  {marker.upper()}  ", f"МАГАЗИН {marker}", f"УЛИЦА {marker}"):
            page = await client.get(BASE_PATH, params={"search": query, "offset": 1, "limit": 1})
            assert page.status_code == 200
            body = page.json()
            assert body["total"] == 3
            assert body["offset"] == 1
            assert body["limit"] == 1
            assert [row["clientId"] for row in body["data"]["clients"]] == [rows[1]["clientId"]]
        phone = await client.get(BASE_PATH, params={"search": "912 345-67-01"})
        assert phone.status_code == 200
        assert phone.json()["total"] == 1
        assert phone.json()["data"]["clients"][0]["clientId"] == rows[1]["clientId"]
        deactivated = await client.patch(f"{BASE_PATH}/{rows[1]['clientId']}", json={"isActive": False})
        assert deactivated.status_code == 200
        for include, total in ((False, 2), (True, 3)):
            response = await client.get(BASE_PATH, params={"search": marker, "include_deactivated": include})
            assert response.status_code == 200
            assert response.json()["total"] == total
        for query in (uuid4().hex, "%", "_"):
            response = await client.get(BASE_PATH, params={"search": query})
            assert response.status_code == 200
            assert response.json()["total"] == 0
            assert response.json()["data"]["clients"] == []
        blank = await client.get(BASE_PATH, params={"search": "   "})
        unfiltered = await client.get(BASE_PATH)
        assert blank.json() == unfiltered.json()

    @pytest.mark.parametrize("params", [{"offset": -1}, {"limit": 0}, {"search": "x" * 501}])
    async def test_list_validation(self, client: AsyncClient, active_employee: EmployeeTestData, params: dict) -> None:
        await self.login(client, active_employee)
        assert (await client.get(BASE_PATH, params=params)).status_code == 422

    async def test_invalid_uuid_and_unknown_client(
        self, client: AsyncClient, active_employee: EmployeeTestData
    ) -> None:
        await self.login(client, active_employee)
        for value, expected in (("not-a-uuid", 422), (str(uuid4()), 404)):
            assert (await client.get(f"{BASE_PATH}/{value}")).status_code == expected
            assert (await client.patch(f"{BASE_PATH}/{value}", json={"name": "Updated"})).status_code == expected

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("name", ""),
            ("name", "x" * 121),
            ("phone", ""),
            ("phone", "x" * 33),
            ("address", ""),
            ("address", "x" * 501),
            ("sleepingThresholdDays", -1),
            ("sleepingThresholdDays", 3651),
        ],
    )
    async def test_create_and_patch_validation(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        field: str,
        value: object,
    ) -> None:
        await self.login(client, active_employee)
        response = await client.post(f"{BASE_PATH}/create", json=self.payload(**{field: value}))
        assert response.status_code == 422
        created = await client.post(f"{BASE_PATH}/create", json=self.payload())
        assert created.status_code == 201
        original = created.json()["data"]
        for invalid in (value, None):
            response = await client.patch(f"{BASE_PATH}/{original['clientId']}", json={field: invalid})
            assert response.status_code == 422
        after = await client.get(f"{BASE_PATH}/{original['clientId']}")
        assert after.json()["data"] == original

    async def test_relations_null_clearing_and_patch_preserves_other_fields(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)
        rep_response = await client.post(
            "/protected/sales-representatives/create",
            json={
                "name": f"Rep {uuid4()}",
                "phone": uuid4().hex,
                "commissionPercent": 10,
            },
        )
        assert rep_response.status_code == 201
        rep = rep_response.json()["data"]
        method_response = await client.post("/protected/payment-methods/create", json={"name": f"Method {uuid4()}"})
        assert method_response.status_code == 201
        method = method_response.json()["data"]
        for path in (
            f"/protected/sales-representatives/{rep['salesRepresentativeId']}",
            f"/protected/payment-methods/{method['paymentMethodId']}",
        ):
            assert (await client.patch(path, json={"isActive": False})).status_code == 200
        created = await client.post(
            f"{BASE_PATH}/create",
            json=self.payload(
                salesRepresentativeId=rep["salesRepresentativeId"],
                defaultPaymentMethodId=method["paymentMethodId"],
                cooldownUntil="2026-10-12T10:00:00",
                sleepingThresholdDays=0,
            ),
        )
        assert created.status_code == 201
        original = created.json()["data"]
        assert original["salesRepresentativeName"] == rep["name"]
        assert original["defaultPaymentMethodName"] == method["name"]
        assert original["cooldownUntil"] == "2026-10-12T10:00:00"
        path = f"{BASE_PATH}/{original['clientId']}"
        for field in ("salesRepresentativeId", "defaultPaymentMethodId"):
            response = await client.patch(path, json={field: str(uuid4())})
            assert response.status_code == 422
            assert (await client.get(path)).json()["data"] == original
        changed = await client.patch(path, json={"sleepingThresholdDays": 3650})
        assert changed.status_code == 200
        assert changed.json()["data"] == {**original, "sleepingThresholdDays": 3650}
        cleared = await client.patch(
            path,
            json={
                "salesRepresentativeId": None,
                "defaultPaymentMethodId": None,
                "cooldownUntil": None,
            },
        )
        assert cleared.status_code == 200
        after = (await client.get(path)).json()["data"]
        for field in (
            "salesRepresentativeId",
            "salesRepresentativeName",
            "defaultPaymentMethodId",
            "defaultPaymentMethodName",
            "cooldownUntil",
        ):
            assert after[field] is None
        assert after["name"] == original["name"]
        assert after["phone"] == original["phone"]
        assert after["address"] == original["address"]
        assert after["lastDeliveryDate"] is None
        assert after["lastDeliveryQuantity"] is None

    @pytest.mark.parametrize(
        "body",
        [
            {"isActive": None},
            {"clientId": str(uuid4())},
            {"lastDeliveryDate": "2026-10-12T10:00:00"},
            {"lastDeliveryQuantity": 10},
            {"cooldownUntil": "2026-10-12T10:00:00Z"},
            {"cooldownUntil": "2026-10-12T10:00:00+03:00"},
        ],
    )
    async def test_patch_rejects_read_only_fields_and_timezone_offsets(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        body: dict,
    ) -> None:
        await self.login(client, active_employee)
        created = await client.post(f"{BASE_PATH}/create", json=self.payload())
        assert created.status_code == 201
        original = created.json()["data"]
        path = f"{BASE_PATH}/{original['clientId']}"
        response = await client.patch(path, json=body)
        assert response.status_code == 422
        assert (await client.get(path)).json()["data"] == original

    @pytest.mark.parametrize(
        "body",
        [
            {"isActive": False},
            {"lastDeliveryQuantity": 10},
            {"createdAt": "2026-10-12T10:00:00"},
            {"cooldownUntil": "2026-10-12T10:00:00Z"},
        ],
    )
    async def test_create_rejects_server_fields_and_timezone_offsets(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        body: dict,
    ) -> None:
        await self.login(client, active_employee)
        response = await client.post(f"{BASE_PATH}/create", json=self.payload(**body))
        assert response.status_code == 422
