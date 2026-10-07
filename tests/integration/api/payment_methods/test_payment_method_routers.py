from httpx import AsyncClient
from typing import Any

from src.core.uuid7 import uuid7
from tests.integration.conftest import EmployeeTestData


BASE_PATH = "/protected/payment-methods"


class TestPaymentMethodRouters:
    """Интеграционные тесты API способов оплаты."""

    @staticmethod
    async def login(client: AsyncClient, employee: EmployeeTestData) -> None:
        """Вспомогательный метод для авторизации."""
        response = await client.post(
            "/public/auth/login",
            json={"username": employee.username, "password": employee.password},
        )
        assert response.status_code == 200

    @staticmethod
    async def create_payment_method(client: AsyncClient, name: str) -> dict[str, Any]:
        """Вспомогательный метод для создания способа оплаты."""
        response = await client.post(
            f"{BASE_PATH}/create",
            json={"name": name},
        )
        assert response.status_code == 201
        return response.json()["data"]

    async def test_get_payment_methods_filter_active(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        # Создаем два способа оплаты
        pm_active = await self.create_payment_method(client, f"Active PM {uuid7()}")
        pm_inactive = await self.create_payment_method(client, f"Inactive PM {uuid7()}")

        # Деактивируем второй
        await client.patch(
            f"{BASE_PATH}/{pm_inactive['paymentMethodId']}",
            json={"isActive": False},
        )

        # Проверка: только активные
        response = await client.get(f"{BASE_PATH}?include_deactivated=false")
        assert response.status_code == 200
        data = response.json()["data"]["paymentMethods"]

        pm_ids = [pm["paymentMethodId"] for pm in data]
        assert pm_active["paymentMethodId"] in pm_ids
        assert pm_inactive["paymentMethodId"] not in pm_ids

        # Проверка: все способы оплаты
        response_all = await client.get(f"{BASE_PATH}?include_deactivated=true")
        assert response_all.status_code == 200
        data_all = response_all.json()["data"]["paymentMethods"]

        pm_ids_all = [pm["paymentMethodId"] for pm in data_all]
        assert pm_active["paymentMethodId"] in pm_ids_all
        assert pm_inactive["paymentMethodId"] in pm_ids_all

    async def test_get_payment_method_by_id(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        # Активный
        pm_active = await self.create_payment_method(client, f"PM Active {uuid7()}")
        resp_active = await client.get(f"{BASE_PATH}/{pm_active['paymentMethodId']}")
        assert resp_active.status_code == 200
        data_active = resp_active.json()["data"]
        assert data_active["paymentMethodId"] == pm_active["paymentMethodId"]
        assert data_active["isActive"] is True

        # Деактивированный
        pm_inactive = await self.create_payment_method(client, f"PM Inactive {uuid7()}")
        await client.patch(
            f"{BASE_PATH}/{pm_inactive['paymentMethodId']}", 
            json={"isActive": False}
        )

        resp_inactive = await client.get(f"{BASE_PATH}/{pm_inactive['paymentMethodId']}")
        assert resp_inactive.status_code == 200
        data_inactive = resp_inactive.json()["data"]
        assert data_inactive["paymentMethodId"] == pm_inactive["paymentMethodId"]
        assert data_inactive["isActive"] is False

        # Несуществующий
        resp_none = await client.get(f"{BASE_PATH}/{uuid7()}")
        assert resp_none.status_code == 404

    async def test_create_payment_method_success(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        name = f"New PM {uuid7()}"
        payload = {"name": name}
        response = await client.post(f"{BASE_PATH}/create", json=payload)

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == name
        assert data["isActive"] is True
        assert "paymentMethodId" in data

        # Проверка сохранения через GET
        get_resp = await client.get(f"{BASE_PATH}/{data['paymentMethodId']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["name"] == name

    async def test_create_payment_method_duplicate_name(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        name = f"Duplicate PM {uuid7()}"
        await self.create_payment_method(client, name)

        # Повторный POST с тем же именем
        response = await client.post(f"{BASE_PATH}/create", json={"name": name})
        assert response.status_code == 409

    async def test_create_payment_method_similar_names_allowed(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        name_base = f"Similar PM {uuid7()}"
        pm1 = await self.create_payment_method(client, name_base)

        # Создаем запись с похожим именем (добавляем суффикс)
        name_similar = f"{name_base}_v2"
        pm2 = await self.create_payment_method(client, name_similar)

        assert pm1["paymentMethodId"] != pm2["paymentMethodId"]
        assert pm1["name"] != pm2["name"]

    async def test_update_payment_method_scenarios(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)
        pm = await self.create_payment_method(client, f"Original PM {uuid7()}")
        pm_id = pm["paymentMethodId"]

        # Изменение имени
        new_name = f"Updated PM {uuid7()}"
        response = await client.patch(f"{BASE_PATH}/{pm_id}", json={"name": new_name})
        assert response.status_code == 200
        assert response.json()["data"]["name"] == new_name

        # Деактивация
        response = await client.patch(f"{BASE_PATH}/{pm_id}", json={"isActive": False})
        assert response.status_code == 200
        assert response.json()["data"]["isActive"] is False

        # Реактивация
        response = await client.patch(f"{BASE_PATH}/{pm_id}", json={"isActive": True})
        assert response.status_code == 200
        assert response.json()["data"]["isActive"] is True

        # Неизвестный UUID
        response_404 = await client.patch(f"{BASE_PATH}/{uuid7()}", json={"name": "Any"})
        assert response_404.status_code == 404

        # Пустой payload
        response_422 = await client.patch(f"{BASE_PATH}/{pm_id}", json={})
        assert response_422.status_code == 422

    async def test_update_payment_method_duplicate_name(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)
        
        pm1 = await self.create_payment_method(client, f"PM One {uuid7()}")
        pm2 = await self.create_payment_method(client, f"PM Two {uuid7()}")
        
        # Пытаемся изменить имя pm2 на имя pm1
        response = await client.patch(
            f"{BASE_PATH}/{pm2['paymentMethodId']}", 
            json={"name": pm1["name"]}
        )
        assert response.status_code == 409

        # Проверяем, что имя pm2 не изменилось
        get_resp = await client.get(f"{BASE_PATH}/{pm2['paymentMethodId']}")
        assert get_resp.json()["data"]["name"] == pm2["name"]

    async def test_check_duplicate_payment_method(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        # Точное совпадение
        name = f"Unique PM {uuid7()}"
        pm = await self.create_payment_method(client, name)

        response = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": name})
        assert response.status_code == 200
        assert response.json()["data"]["paymentMethodId"] == pm["paymentMethodId"]

        # Без совпадений
        response_none = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": f"Nonexistent {uuid7()}"})
        assert response_none.status_code == 200
        assert response_none.json()["data"] is None

        # Поиск деактивированного
        pm_inactive = await self.create_payment_method(client, f"Inactive PM {uuid7()}")
        await client.patch(f"{BASE_PATH}/{pm_inactive['paymentMethodId']}", json={"isActive": False})

        response_inactive = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": pm_inactive["name"]})
        assert response_inactive.status_code == 200
        assert response_inactive.json()["data"]["paymentMethodId"] == pm_inactive["paymentMethodId"]

        # Частичное совпадение (similarity >= 0.35)
        suffix = f"_{uuid7().hex[:6]}"
        name_query = "Alexander"
        name_full = f"Alexander{suffix}"
        pm_alex = await self.create_payment_method(client, name_full)

        response_partial = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": name_query})
        assert response_partial.status_code == 200
        assert response_partial.json()["data"]["paymentMethodId"] == pm_alex["paymentMethodId"]

    async def test_unauthorized_access(
        self,
        client: AsyncClient,
    ) -> None:
        # Без входа
        response = await client.get(f"{BASE_PATH}")
        assert response.status_code == 401
