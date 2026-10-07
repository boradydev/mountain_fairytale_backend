from httpx import AsyncClient
from typing import Any

from src.core.uuid7 import uuid7
from tests.integration.conftest import EmployeeTestData
from tests.helpers import unique_product_name


BASE_PATH = "/protected/products"


class TestProductRouters:
    """Интеграционные тесты API товаров."""

    @staticmethod
    async def login(client: AsyncClient, employee: EmployeeTestData) -> None:
        """Вспомогательный метод для авторизации."""
        response = await client.post(
            "/public/app/login",
            json={"username": employee.username, "password": employee.password},
        )
        assert response.status_code == 200

    @staticmethod
    async def create_product(client: AsyncClient, name: str, base_price: float) -> dict[str, Any]:
        """Вспомогательный метод для создания товара."""
        response = await client.post(
            f"{BASE_PATH}/create",
            json={"name": name, "basePrice": base_price},
        )
        assert response.status_code == 201
        return response.json()["data"]

    async def test_get_products_filter_active(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        # Создаем активный и деактивированный товары
        p_active = await self.create_product(client, unique_product_name("Active"), 100.0)
        p_inactive = await self.create_product(client, unique_product_name("Inactive"), 200.0)

        # Деактивируем второй
        await client.patch(
            f"{BASE_PATH}/{p_inactive['productId']}",
            json={"isActive": False},
        )

        # Проверка: только активные
        response = await client.get(f"{BASE_PATH}?include_deactivated=false")
        assert response.status_code == 200
        data = response.json()["data"]["app"]
        product_ids = [p["productId"] for p in data]
        assert p_active["productId"] in product_ids
        assert p_inactive["productId"] not in product_ids

        # Проверка: все товары
        response_all = await client.get(f"{BASE_PATH}?include_deactivated=true")
        assert response_all.status_code == 200
        data_all = response_all.json()["data"]["app"]
        product_ids_all = [p["productId"] for p in data_all]
        assert p_active["productId"] in product_ids_all
        assert p_inactive["productId"] in product_ids_all

    async def test_get_product_by_id(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        # Активный товар
        name = unique_product_name("ID Test")
        price = 500.0
        p = await self.create_product(client, name, price)
        
        resp = await client.get(f"{BASE_PATH}/{p['productId']}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["productId"] == p["productId"]
        assert data["name"] == name
        assert data["basePrice"] == price
        assert data["isActive"] is True

        # Деактивация и повторный GET
        await client.patch(f"{BASE_PATH}/{p['productId']}", json={"isActive": False})
        resp_inactive = await client.get(f"{BASE_PATH}/{p['productId']}")
        assert resp_inactive.status_code == 200
        data_inactive = resp_inactive.json()["data"]
        assert data_inactive["isActive"] is False
        assert data_inactive["name"] == name
        assert data_inactive["basePrice"] == price

        # Несуществующий UUID
        resp_none = await client.get(f"{BASE_PATH}/{uuid7()}")
        assert resp_none.status_code == 404

    async def test_create_product_scenarios(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        # 1. Успешное создание
        name = unique_product_name("Valid")
        price = 123.45
        payload = {"name": name, "basePrice": price}
        response = await client.post(f"{BASE_PATH}/create", json=payload)
        
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == name
        assert data["basePrice"] == price
        assert data["isActive"] is True
        product_id = data["productId"]

        # Проверка через GET
        get_resp = await client.get(f"{BASE_PATH}/{product_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["name"] == name

        # 2. Дубликат имени (точное совпадение) -> 409
        resp_dup = await client.post(f"{BASE_PATH}/create", json=payload)
        assert resp_dup.status_code == 409

        # 3. Разный регистр и пробелы (должны быть допустимы)
        # Регистр
        resp_case = await client.post(
            f"{BASE_PATH}/create", 
            json={"name": name.lower(), "basePrice": price}
        )
        assert resp_case.status_code == 201
        
        # Пробел
        resp_space = await client.post(
            f"{BASE_PATH}/create", 
            json={"name": f" {name}", "basePrice": price}
        )
        assert resp_space.status_code == 201

        # 4. Валидация схемы (422)
        # Пустое имя
        assert (await client.post(f"{BASE_PATH}/create", json={"name": "", "basePrice": 10})).status_code == 422
        # Слишком длинное имя (>120)
        assert (await client.post(f"{BASE_PATH}/create", json={"name": "a" * 121, "basePrice": 10})).status_code == 422
        # Цена < 0
        assert (await client.post(f"{BASE_PATH}/create", json={"name": unique_product_name("PriceLow"), "basePrice": -1})).status_code == 422
        # Цена > 1 000 000 000
        assert (await client.post(f"{BASE_PATH}/create", json={"name": unique_product_name("PriceHigh"), "basePrice": 1_000_000_001})).status_code == 422

        # 5. Граничные значения цены (0 и 1 000 000 000)
        assert (await client.post(f"{BASE_PATH}/create", json={"name": unique_product_name("MinPrice"), "basePrice": 0})).status_code == 201
        assert (await client.post(f"{BASE_PATH}/create", json={"name": unique_product_name("MaxPrice"), "basePrice": 1_000_000_000})).status_code == 201

    async def test_update_product_scenarios(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)
        
        p = await self.create_product(client, unique_product_name("Original"), 100.0)
        p_id = p["productId"]

        # 1. Изменение имени и цены
        new_name = unique_product_name("Updated")
        new_price = 200.0
        resp = await client.patch(f"{BASE_PATH}/{p_id}", json={"name": new_name, "basePrice": new_price})
        assert resp.status_code == 200
        
        get_resp = await client.get(f"{BASE_PATH}/{p_id}")
        data = get_resp.json()["data"]
        assert data["name"] == new_name
        assert data["basePrice"] == new_price

        # 2. Цикл активации/деактивации
        # Деактивация
        await client.patch(f"{BASE_PATH}/{p_id}", json={"isActive": False})
        assert (await client.get(f"{BASE_PATH}/{p_id}")).json()["data"]["isActive"] is False
        
        # Реактивация
        await client.patch(f"{BASE_PATH}/{p_id}", json={"isActive": True})
        assert (await client.get(f"{BASE_PATH}/{p_id}")).json()["data"]["isActive"] is True

        # 3. Конфликт имени при обновлении
        p2 = await self.create_product(client, unique_product_name("Other"), 10.0)
        resp_conflict = await client.patch(f"{BASE_PATH}/{p_id}", json={"name": p2["name"]})
        assert resp_conflict.status_code == 409
        
        # Проверка, что имя не изменилось
        assert (await client.get(f"{BASE_PATH}/{p_id}")).json()["data"]["name"] == new_name

        # 4. Ошибки PATCH
        assert (await client.patch(f"{BASE_PATH}/{p_id}", json={})).status_code == 422
        assert (await client.patch(f"{BASE_PATH}/{uuid7()}", json={"name": "Any"})).status_code == 404

    async def test_check_duplicate_scenarios(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        # 1. Точное совпадение
        name = unique_product_name("Unique")
        p = await self.create_product(client, name, 100.0)
        
        resp = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": name})
        assert resp.status_code == 200
        assert resp.json()["data"]["productId"] == p["productId"]

        # 2. Без совпадений
        resp_none = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": unique_product_name("Nonexistent")})
        assert resp_none.status_code == 200
        assert resp_none.json()["data"] is None

        # 3. Частичное совпадение
        query_name = unique_product_name("Alexander")
        full_name = f"{query_name}_Candidate"
        p_alex = await self.create_product(client, full_name, 100.0)
        
        resp_partial = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": query_name})
        assert resp_partial.status_code == 200
        assert resp_partial.json()["data"]["productId"] == p_alex["productId"]

        # 4. Поиск деактивированного
        await client.patch(f"{BASE_PATH}/{p_alex['productId']}", json={"isActive": False})
        resp_inact = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": query_name})
        assert resp_inact.status_code == 200
        assert resp_inact.json()["data"]["productId"] == p_alex["productId"]

        # 5. Точное совпадение выше частичного
        # Создаем товар с именем query_name (точное)
        p_exact = await self.create_product(client, query_name, 100.0)
        resp_rank = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": query_name})
        assert resp_rank.json()["data"]["productId"] == p_exact["productId"]

    async def test_unauthorized_access(
        self,
        client: AsyncClient,
    ) -> None:
        # Без входа
        response = await client.get(f"{BASE_PATH}")
        assert response.status_code == 401
