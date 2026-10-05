from httpx import AsyncClient
from uuid import UUID

from tests.integration.conftest import EmployeeTestData
from src.core.uuid7 import uuid7
from tests.helpers import unique_username


BASE_PATH = "/protected/employees"


class TestEmployeeRouters:
    """Интеграционные тесты API сотрудников.
    
    Согласно контракту: доступ только для администраторов.
    """

    @staticmethod
    async def login(client: AsyncClient, employee: EmployeeTestData):
        """Вспомогательный метод для авторизации."""
        await client.post(
            "/public/auth/login",
            json={"username": employee.username, "password": employee.password},
        )

    async def test_get_employees_filter_active(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        employee_factory,
    ) -> None:
        await self.login(client, active_employee)

        # Создаем одного активного и одного деактивированного
        active_emp = await employee_factory(username=unique_username("active"))
        inactive_emp = await employee_factory(username=unique_username("inactive"), is_active=False)

        # По умолчанию include_deactivated=false
        response = await client.get(f"{BASE_PATH}?include_deactivated=false")
        assert response.status_code == 200
        data = response.json()["data"]["employees"]
        
        emp_ids = [emp["employeeId"] for emp in data]
        assert str(active_emp.employee_id) in emp_ids
        assert str(inactive_emp.employee_id) not in emp_ids

    async def test_get_employees_include_all(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        employee_factory,
    ) -> None:
        await self.login(client, active_employee)

        active_emp = await employee_factory(username=unique_username("active_all"))
        inactive_emp = await employee_factory(username=unique_username("inactive_all"), is_active=False)

        response = await client.get(f"{BASE_PATH}?include_deactivated=true")
        assert response.status_code == 200
        data = response.json()["data"]["employees"]
        
        emp_ids = [emp["employeeId"] for emp in data]
        assert str(active_emp.employee_id) in emp_ids
        assert str(inactive_emp.employee_id) in emp_ids

    async def test_get_employee_success(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        employee_factory,
    ) -> None:
        await self.login(client, active_employee)
        
        # Тест для активного
        active_emp = await employee_factory()
        resp_active = await client.get(f"{BASE_PATH}/{active_emp.employee_id}")
        assert resp_active.status_code == 200
        assert resp_active.json()["data"]["employeeId"] == str(active_emp.employee_id)

        # Тест для деактивированного
        inactive_emp = await employee_factory(is_active=False)
        resp_inactive = await client.get(f"{BASE_PATH}/{inactive_emp.employee_id}")
        assert resp_inactive.status_code == 200
        assert resp_inactive.json()["data"]["employeeId"] == str(inactive_emp.employee_id)

    async def test_get_employee_not_found(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)
        response = await client.get(f"{BASE_PATH}/{uuid7()}")
        assert response.status_code == 404

    async def test_create_employee_success(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        payload = {
            "username": unique_username("new_user"),
            "password": "strong_password123"
        }
        response = await client.post(f"{BASE_PATH}/create", json=payload)
        assert response.status_code == 201
        
        data = response.json()["data"]
        assert data["username"] == payload["username"]
        assert data["isActive"] is True
        assert "employeeId" in data

        # Проверка через GET
        get_resp = await client.get(f"{BASE_PATH}/{data['employeeId']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["username"] == payload["username"]

    async def test_create_employee_empty_password(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        payload = {
            "username": unique_username("empty_pass"),
            "password": ""
        }
        response = await client.post(f"{BASE_PATH}/create", json=payload)
        assert response.status_code == 201
        assert response.json()["data"]["username"] == payload["username"]

    async def test_update_employee_username(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        employee_factory,
    ) -> None:
        await self.login(client, active_employee)
        emp = await employee_factory()

        payload = {"username": unique_username("updated")}
        response = await client.patch(f"{BASE_PATH}/{emp.employee_id}", json=payload)
        assert response.status_code == 200
        assert response.json()["data"]["username"] == payload["username"]

    async def test_update_employee_activation_cycle(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        employee_factory,
    ) -> None:
        await self.login(client, active_employee)
        emp = await employee_factory(is_active=True)

        # Деактивация
        response = await client.patch(f"{BASE_PATH}/{emp.employee_id}", json={"is_active": False})
        assert response.status_code == 200
        assert response.json()["data"]["isActive"] is False

        # Реактивация
        response = await client.patch(f"{BASE_PATH}/{emp.employee_id}", json={"is_active": True})
        assert response.status_code == 200
        assert response.json()["data"]["isActive"] is True

    async def test_update_employee_not_found(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)
        response = await client.patch(f"{BASE_PATH}/{uuid7()}", json={"username": "any"})
        assert response.status_code == 404

    async def test_update_employee_empty_payload(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        employee_factory,
    ) -> None:
        await self.login(client, active_employee)
        emp = await employee_factory()

        # Пустой запрос {} должен вернуть 422 согласно контракту
        response = await client.patch(f"{BASE_PATH}/{emp.employee_id}", json={})
        assert response.status_code == 422

    async def test_change_password_success(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        employee_factory,
    ) -> None:
        await self.login(client, active_employee)
        emp = await employee_factory()

        # Запоминаем состояние до смены пароля
        before_resp = await client.get(f"{BASE_PATH}/{emp.employee_id}")
        before_data = before_resp.json()["data"]

        payload = {"password": "new_secure_password_123"}
        response = await client.put(f"{BASE_PATH}/{emp.employee_id}/change-password", json=payload)
        assert response.status_code == 200
        assert response.json()["message"] == "Пароль сотрудника изменён."

        # Проверяем, что остальные поля не изменились
        after_resp = await client.get(f"{BASE_PATH}/{emp.employee_id}")
        after_data = after_resp.json()["data"]
        
        assert after_data["username"] == before_data["username"]
        assert after_data["role"] == before_data["role"]
        assert after_data["isActive"] == before_data["isActive"]
        assert after_data["employeeId"] == before_data["employeeId"]

    async def test_change_password_empty(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        employee_factory,
    ) -> None:
        await self.login(client, active_employee)
        emp = await employee_factory()

        payload = {"password": ""}
        response = await client.put(f"{BASE_PATH}/{emp.employee_id}/change-password", json=payload)
        assert response.status_code == 200

    async def test_change_password_not_found(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)
        response = await client.put(f"{BASE_PATH}/{uuid7()}/change-password", json={"password": "any"})
        assert response.status_code == 404
