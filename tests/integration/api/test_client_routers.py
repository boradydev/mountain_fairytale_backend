from uuid import uuid4

from httpx import AsyncClient

from src.core.uuid7 import uuid7
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
            "address": "Client test address",
            "sleepingThresholdDays": 30,
        }
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

        assert (
            await client.patch(f"{BASE_PATH}/{first['clientId']}", json={})
        ).status_code == 422

    async def test_list_pagination_and_deactivated_record(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)
        created = []
        for index in range(3):
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
        assert active_data["total"] == 2
        assert active_data["limit"] == 1
        assert len(active_data["data"]["clients"]) == 1

        all_clients = await client.get(
            BASE_PATH,
            params={"include_deactivated": True, "offset": 0, "limit": 10},
        )
        assert all_clients.status_code == 200
        all_data = all_clients.json()
        assert all_data["total"] == 3
        assert len(all_data["data"]["clients"]) == 3

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
