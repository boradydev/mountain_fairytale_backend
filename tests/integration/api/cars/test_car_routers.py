from httpx import AsyncClient
from src.core.uuid7 import uuid7

from tests.integration.conftest import EmployeeTestData
from tests.helpers import unique_car_number


BASE_PATH = "/protected/cars"


class TestCarRouters:
    """Интеграционные тесты API автомобилей."""

    @staticmethod
    async def login(client: AsyncClient, employee: EmployeeTestData):
        """Вспомогательный метод для авторизации."""
        await client.post(
            "/public/auth/login",
            json={"username": employee.username, "password": employee.password},
        )

    async def test_get_cars_filter_active(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        car_factory,
    ) -> None:
        await self.login(client, active_employee)

        # Создаем конкретные объекты, чтобы знать их ID
        active_car = await car_factory(is_active=True)
        inactive_car = await car_factory(is_active=False)

        # По умолчанию include_deactivated=False
        response = await client.get(f"{BASE_PATH}?include_deactivated=false")
        assert response.status_code == 200
        data = response.json()["data"]["cars"]
        
        # Проверяем, что активный автомобиль в списке, а деактивированный — нет
        car_ids = [car["carId"] for car in data]
        assert str(active_car.car_id) in car_ids
        assert str(inactive_car.car_id) not in car_ids

    async def test_get_cars_include_all(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        car_factory,
    ) -> None:
        await self.login(client, active_employee)

        active_car = await car_factory(is_active=True)
        inactive_car = await car_factory(is_active=False)

        response = await client.get(f"{BASE_PATH}?include_deactivated=true")
        assert response.status_code == 200
        data = response.json()["data"]["cars"]
        
        car_ids = [car["carId"] for car in data]
        assert str(active_car.car_id) in car_ids
        assert str(inactive_car.car_id) in car_ids

    async def test_check_duplicate_exists(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        car_factory,
    ) -> None:
        await self.login(client, active_employee)
        car = await car_factory()

        response = await client.get(f"{BASE_PATH}/check-duplicate", params={"number": car.number})
        assert response.status_code == 200
        assert response.json()["data"]["carId"] == str(car.car_id)

    async def test_check_duplicate_not_found(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        response = await client.get(
            f"{BASE_PATH}/check-duplicate", params={"number": "NONEXISTENT"}
        )
        assert response.status_code == 200
        assert response.json()["data"] is None

    async def test_create_car_success(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        payload = {
            "model": "Toyota Camry", 
            "number": unique_car_number(), 
            "currentMileage": 100.0
        }
        response = await client.post(f"{BASE_PATH}/create", json=payload)

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["model"] == payload["model"]
        assert data["isActive"] is True

        # Проверка через GET
        get_resp = await client.get(f"{BASE_PATH}/{data['carId']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["number"] == payload["number"]

    async def test_create_car_duplicate_number(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        car_factory,
    ) -> None:
        await self.login(client, active_employee)
        car = await car_factory()

        payload = {"model": "Tesla", "number": car.number}
        response = await client.post(f"{BASE_PATH}/create", json=payload)
        assert response.status_code == 409

    async def test_create_car_duplicate_number_with_deactivated(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        car_factory,
    ) -> None:
        await self.login(client, active_employee)
        
        # Создаем деактивированный автомобиль с определенным номером
        car = await car_factory(is_active=False)

        # Пытаемся создать новый активный автомобиль с тем же номером
        payload = {"model": "Tesla", "number": car.number}
        response = await client.post(f"{BASE_PATH}/create", json=payload)
        
        # Ожидаем 409 Conflict, так как номер должен быть уникальным во всей системе
        assert response.status_code == 409

    async def test_update_car_partial(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        car_factory,
    ) -> None:
        await self.login(client, active_employee)
        car = await car_factory(model="Old Model")

        payload = {"model": "New Model"}
        response = await client.patch(f"{BASE_PATH}/{car.car_id}", json=payload)

        assert response.status_code == 200
        assert response.json()["data"]["model"] == "New Model"
        assert response.json()["data"]["number"] == car.number

    async def test_update_car_duplicate_number(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        car_factory,
    ) -> None:
        await self.login(client, active_employee)
        
        # Создаем два автомобиля
        car1 = await car_factory()
        car2 = await car_factory()

        # Пытаемся изменить номер первого автомобиля на номер второго
        payload = {"number": car2.number}
        response = await client.patch(f"{BASE_PATH}/{car1.car_id}", json=payload)
        
        assert response.status_code == 409

    async def test_update_car_not_found(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)
        response = await client.patch(f"{BASE_PATH}/{uuid7()}", json={"model": "Any"})
        assert response.status_code == 404

    async def test_unauthorized_access(
        self,
        client: AsyncClient,
    ) -> None:
        # Без логина
        response = await client.get(f"{BASE_PATH}")
        assert response.status_code == 401
