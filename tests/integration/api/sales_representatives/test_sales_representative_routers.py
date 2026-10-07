from datetime import datetime
from httpx import AsyncClient
from typing import Any
from uuid import UUID

from src.core.uuid7 import uuid7
from tests.integration.conftest import EmployeeTestData
from tests.helpers import unique_phone


BASE_PATH = "/protected/sales-representatives"


class TestSalesRepresentativeRouters:
    """Интеграционные тесты API торговых представителей."""

    @staticmethod
    async def login(client: AsyncClient, employee: EmployeeTestData) -> None:
        """Вспомогательный метод для авторизации."""
        response = await client.post(
            "/public/auth/login",
            json={"username": employee.username, "password": employee.password},
        )
        assert response.status_code == 200

    @staticmethod
    async def create_sales_representative(
        client: AsyncClient, name: str, phone: str, commission_percent: float = 10.0
    ) -> dict[str, Any]:
        """Вспомогательный метод для создания торгового представителя."""
        response = await client.post(
            f"{BASE_PATH}/create",
            json={
                "name": name,
                "phone": phone,
                "commissionPercent": commission_percent,
            },
        )
        assert response.status_code == 201
        return response.json()["data"]

    async def test_get_sales_representatives_filter_active(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        # Создаем двух представителей
        rep1 = await self.create_sales_representative(client, f"Rep 1 {uuid7()}", unique_phone())
        rep2 = await self.create_sales_representative(client, f"Rep 2 {uuid7()}", unique_phone())

        # Деактивируем одного
        await client.patch(
            f"{BASE_PATH}/{rep2['salesRepresentativeId']}",
            json={"isActive": False},
        )

        # Проверка: только активные (по умолчанию или explicit false)
        resp_active = await client.get(f"{BASE_PATH}?include_deactivated=false")
        assert resp_active.status_code == 200
        data_active = resp_active.json()["data"]["salesRepresentatives"]
        ids_active = [r["salesRepresentativeId"] for r in data_active]
        assert rep1["salesRepresentativeId"] in ids_active
        assert rep2["salesRepresentativeId"] not in ids_active

        # Проверка: все представители
        resp_all = await client.get(f"{BASE_PATH}?include_deactivated=true")
        assert resp_all.status_code == 200
        data_all = resp_all.json()["data"]["salesRepresentatives"]
        ids_all = [r["salesRepresentativeId"] for r in data_all]
        assert rep1["salesRepresentativeId"] in ids_all
        assert rep2["salesRepresentativeId"] in ids_all

    async def test_get_sales_representative_by_id(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        name = f"ID Test {uuid7()}"
        phone = unique_phone()
        rep = await self.create_sales_representative(client, name, phone)
        rep_id = rep["salesRepresentativeId"]

        # Проверка активного
        resp = await client.get(f"{BASE_PATH}/{rep_id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["salesRepresentativeId"] == rep_id
        assert data["name"] == name
        assert data["phone"] == phone
        assert data["isActive"] is True

        # Деактивация и повторный GET
        await client.patch(f"{BASE_PATH}/{rep_id}", json={"isActive": False})
        resp_inactive = await client.get(f"{BASE_PATH}/{rep_id}")
        assert resp_inactive.status_code == 200
        data_inactive = resp_inactive.json()["data"]
        assert data_inactive["isActive"] is False
        assert data_inactive["name"] == name
        assert data_inactive["phone"] == phone

        # Несуществующий UUID
        resp_none = await client.get(f"{BASE_PATH}/{uuid7()}")
        assert resp_none.status_code == 404

    async def test_create_and_phone_conflict(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        name = f"Conflict Test {uuid7()}"
        phone = unique_phone()
        comm = 15.5
        
        # Успешное создание
        rep = await self.create_sales_representative(client, name, phone, comm)
        assert rep["name"] == name
        assert rep["phone"] == phone
        assert rep["commissionPercent"] == comm
        assert rep["isActive"] is True
        assert "salesRepresentativeId" in rep

        # Проверка сохранения через GET
        get_resp = await client.get(f"{BASE_PATH}/{rep['salesRepresentativeId']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["phone"] == phone

        # Повторное создание с тем же телефоном -> 409
        resp_conflict = await client.post(
            f"{BASE_PATH}/create",
            json={"name": "Another Name", "phone": phone, "commissionPercent": 10.0},
        )
        assert resp_conflict.status_code == 409

    async def test_update_and_activation_cycle(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        rep = await self.create_sales_representative(client, "Old Name", unique_phone())
        rep_id = rep["salesRepresentativeId"]

        # Обновление данных
        new_name = f"New Name {uuid7()}"
        new_phone = unique_phone()
        new_comm = 20.0
        
        patch_resp = await client.patch(
            f"{BASE_PATH}/{rep_id}",
            json={"name": new_name, "phone": new_phone, "commissionPercent": new_comm},
        )
        assert patch_resp.status_code == 200
        
        get_resp = await client.get(f"{BASE_PATH}/{rep_id}")
        data = get_resp.json()["data"]
        assert data["name"] == new_name
        assert data["phone"] == new_phone
        assert data["commissionPercent"] == new_comm

        # Деактивация
        await client.patch(f"{BASE_PATH}/{rep_id}", json={"isActive": False})
        assert (await client.get(f"{BASE_PATH}/{rep_id}")).json()["data"]["isActive"] is False

        # Реактивация
        await client.patch(f"{BASE_PATH}/{rep_id}", json={"isActive": True})
        assert (await client.get(f"{BASE_PATH}/{rep_id}")).json()["data"]["isActive"] is True

        # Ошибки
        assert (await client.patch(f"{BASE_PATH}/{uuid7()}", json={"name": "Any"})).status_code == 404
        assert (await client.patch(f"{BASE_PATH}/{rep_id}", json={})).status_code == 422

    async def test_update_phone_conflict(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        rep1 = await self.create_sales_representative(client, "Rep 1", unique_phone())
        rep2 = await self.create_sales_representative(client, "Rep 2", unique_phone())

        # Пытаемся изменить телефон rep2 на телефон rep1
        resp = await client.patch(
            f"{BASE_PATH}/{rep2['salesRepresentativeId']}",
            json={"phone": rep1["phone"]},
        )
        assert resp.status_code == 409

        # Проверяем, что данные rep2 не изменились
        get_resp = await client.get(f"{BASE_PATH}/{rep2['salesRepresentativeId']}")
        assert get_resp.json()["data"]["phone"] == rep2["phone"]

    async def test_check_duplicate_scenarios(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        name = f"AlexanderX_{uuid7().hex[:5]}"
        phone = unique_phone()
        rep = await self.create_sales_representative(client, name, phone)
        rep_id = rep["salesRepresentativeId"]

        # 1. Точное совпадение
        resp = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": name, "phone": phone})
        assert resp.status_code == 200
        assert resp.json()["data"]["salesRepresentativeId"] == rep_id

        # 2. Отсутствие совпадений
        resp_none = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": "Nobody", "phone": unique_phone()})
        assert resp_none.json()["data"] is None

        # 3. Похожее имя и телефон (одна цифра в телефоне изменена)
        # name: Alexander -> AlexanderX (similarity >= 0.35)
        query_name = name.replace("X", "")
        query_phone = phone[: -1] + ("1" if phone[-1] != "1" else "2")
        
        resp_sim = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": query_name, "phone": query_phone})
        assert resp_sim.json()["data"]["salesRepresentativeId"] == rep_id

        # 4. Непохожее имя при точном телефоне
        resp_name_fail = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": "TotallyDifferentName", "phone": phone})
        assert resp_name_fail.json()["data"] is None

        # 5. Точное имя при непохожем телефоне
        resp_phone_fail = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": name, "phone": unique_phone()})
        assert resp_phone_fail.json()["data"] is None

        # 6. Поиск деактивированного
        rep_inact = await self.create_sales_representative(client, "Inactive Rep", unique_phone())
        await client.patch(f"{BASE_PATH}/{rep_inact['salesRepresentativeId']}", json={"isActive": False})
        
        resp_inact = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": "Inactive Rep", "phone": rep_inact["phone"]})
        assert resp_inact.json()["data"]["salesRepresentativeId"] == rep_inact["salesRepresentativeId"]

    async def test_duplicate_score_ranking(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        await self.login(client, active_employee)

        # Создаем двух кандидатов с одинаковым именем и очень похожими телефонами
        name = "RankTest"
        phone_query = unique_phone()
        
        # Чтобы они имели одинаковый score, они должны отличаться от запроса одинаково (в одной позиции)
        # Находим два разных символа, не равных последнему символу phone_query
        last_char = phone_query[-1]
        chars = "0123456789abcdef"
        available_chars = [c for c in chars if c != last_char]
        
        phone1 = phone_query[:-1] + available_chars[0]
        phone2 = phone_query[:-1] + available_chars[1]

        rep1 = await self.create_sales_representative(client, name, phone1)
        rep2 = await self.create_sales_representative(client, name, phone2)

        # Поиск
        resp = await client.get(f"{BASE_PATH}/check-duplicate", params={"name": name, "phone": phone_query})
        data = resp.json()["data"]
        
        # Определяем, кто из них "лучше" по контракту (createdAt DESC, then ID DESC)
        dt1 = datetime.fromisoformat(rep1["createdAt"].replace("Z", "+00:00"))
        dt2 = datetime.fromisoformat(rep2["createdAt"].replace("Z", "+00:00"))
        id1 = UUID(rep1["salesRepresentativeId"])
        id2 = UUID(rep2["salesRepresentativeId"])

        if dt1 > dt2:
            expected_id = rep1["salesRepresentativeId"]
        elif dt2 > dt1:
            expected_id = rep2["salesRepresentativeId"]
        else:
            expected_id = rep1["salesRepresentativeId"] if id1 > id2 else rep2["salesRepresentativeId"]

        assert data["salesRepresentativeId"] == expected_id

    async def test_unauthorized_access(
        self,
        client: AsyncClient,
    ) -> None:
        # Без входа
        response = await client.get(f"{BASE_PATH}")
        assert response.status_code == 401
