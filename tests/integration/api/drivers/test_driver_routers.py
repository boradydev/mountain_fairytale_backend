from httpx import AsyncClient
from typing import Any

from src.core.uuid7 import uuid7
from tests.integration.conftest import EmployeeTestData


BASE_PATH = "/protected/app"


class TestDriverRouters:
    """Интеграционные тесты API водителей."""

    @staticmethod
    async def login(client: AsyncClient, employee: EmployeeTestData) -> None:
        """Вспомогательный метод для авторизации."""
        await client.post(
            "/public/app/login",
            json={"username": employee.username, "password": employee.password},
        )

    @staticmethod
    async def create_driver(client: AsyncClient, name: str) -> dict[str, Any]:
        """Вспомогательный метод для создания водителя."""
        response = await client.post(
            f"{BASE_PATH}/create",
            json={"name": name},
        )
        assert response.status_code == 201
        return response.json()["data"]

    async def test_get_drivers_filter_active(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        # Создаем активного и деактивированного водителей
        driver_active = await self.create_driver(client, f"Active Driver {uuid7()}")
        driver_inactive = await self.create_driver(client, f"Inactive Driver {uuid7()}")

        # Деактивируем второго
        await client.patch(
            f"{BASE_PATH}/{driver_inactive['driverId']}",
            json={"isActive": False},
        )

        # Проверка: только активные
        response = await client.get(f"{BASE_PATH}?include_deactivated=false")
        assert response.status_code == 200
        data = response.json()["data"]["app"]

        driver_ids = [d["driverId"] for d in data]
        assert driver_active["driverId"] in driver_ids
        assert driver_inactive["driverId"] not in driver_ids

        # Проверка: все водители
        response_all = await client.get(f"{BASE_PATH}?include_deactivated=true")
        assert response_all.status_code == 200
        data_all = response_all.json()["data"]["app"]

        driver_ids_all = [d["driverId"] for d in data_all]
        assert driver_active["driverId"] in driver_ids_all
        assert driver_inactive["driverId"] in driver_ids_all

    async def test_get_driver_by_id(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        # Активный
        d_active = await self.create_driver(client, f"Driver {uuid7()}")
        resp_active = await client.get(f"{BASE_PATH}/{d_active['driverId']}")
        assert resp_active.status_code == 200
        data_active = resp_active.json()["data"]
        assert data_active["driverId"] == d_active["driverId"]
        assert data_active["name"] == d_active["name"]
        assert data_active["isActive"] is True

        # Деактивированный
        d_inactive = await self.create_driver(client, f"Driver {uuid7()}")
        await client.patch(f"{BASE_PATH}/{d_inactive['driverId']}", json={"isActive": False})

        resp_inactive = await client.get(f"{BASE_PATH}/{d_inactive['driverId']}")
        assert resp_inactive.status_code == 200
        data_inactive = resp_inactive.json()["data"]
        assert data_inactive["driverId"] == d_inactive["driverId"]
        assert data_inactive["isActive"] is False

        # Несуществующий
        resp_none = await client.get(f"{BASE_PATH}/{uuid7()}")
        assert resp_none.status_code == 404

    async def test_create_driver_success(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        name = f"New Driver {uuid7()}"
        payload = {"name": name}
        response = await client.post(f"{BASE_PATH}/create", json=payload)

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == name
        assert data["isActive"] is True
        assert "driverId" in data

        # Проверка сохранения через GET
        get_resp = await client.get(f"{BASE_PATH}/{data['driverId']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["name"] == name

    async def test_update_driver_scenarios(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)
        driver = await self.create_driver(client, f"Original Name {uuid7()}")
        driver_id = driver["driverId"]

        # Изменение имени
        new_name = f"Updated Name {uuid7()}"
        response = await client.patch(f"{BASE_PATH}/{driver_id}", json={"name": new_name})
        assert response.status_code == 200
        assert response.json()["data"]["name"] == new_name

        # Деактивация
        response = await client.patch(f"{BASE_PATH}/{driver_id}", json={"isActive": False})
        assert response.status_code == 200
        assert response.json()["data"]["isActive"] is False

        # Реактивация
        response = await client.patch(f"{BASE_PATH}/{driver_id}", json={"isActive": True})
        assert response.status_code == 200
        assert response.json()["data"]["isActive"] is True

        # Неизвестный UUID
        response_404 = await client.patch(f"{BASE_PATH}/{uuid7()}", json={"name": "Any"})
        assert response_404.status_code == 404

        # Пустой payload
        response_422 = await client.patch(f"{BASE_PATH}/{driver_id}", json={})
        assert response_422.status_code == 422

    async def test_check_duplicate_driver(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        # Точное совпадение
        name = f"Unique Driver {uuid7()}"
        driver = await self.create_driver(client, name)

        response = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": name})
        assert response.status_code == 200
        assert response.json()["data"]["driverId"] == driver["driverId"]

        # Без совпадений
        response_none = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": f"Nonexistent {uuid7()}"})
        assert response_none.status_code == 200
        assert response_none.json()["data"] is None

        # Поиск деактивированного
        d_inactive = await self.create_driver(client, f"Inactive Duplicate {uuid7()}")
        await client.patch(f"{BASE_PATH}/{d_inactive['driverId']}", json={"isActive": False})

        response_inactive = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": d_inactive["name"]})
        assert response_inactive.status_code == 200
        assert response_inactive.json()["data"]["driverId"] == d_inactive["driverId"]

        # Частичное совпадение (similarity >= 0.35)
        suffix = f"_{uuid7().hex[:6]}"
        name_full = f"Alexander{suffix}"
        driver_alex = await self.create_driver(client, name_full)

        response_partial = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": "Alexander"})
        assert response_partial.status_code == 200
        assert response_partial.json()["data"]["driverId"] == driver_alex["driverId"]

    async def test_unauthorized_access(
        self,
        client: AsyncClient,
    ) -> None:
        # Без входа
        response = await client.get(f"{BASE_PATH}")
        assert response.status_code == 401
