from datetime import date
from typing import Any

import pytest
from httpx import AsyncClient

from src.core.uuid7 import uuid7
from tests.helpers import unique_product_name, unique_phone
from tests.integration.conftest import EmployeeTestData


DELIVERY_BASE_PATH = "/protected/delivery-route-sheets"
PICKUP_BASE_PATH = "/protected/pickup-sheets"


class TestDeliveryDocumentRouters:
    """Интеграционные тесты API маршрутных листов и листов самовывоза."""

    @staticmethod
    async def login(client: AsyncClient, employee: EmployeeTestData) -> None:
        response = await client.post(
            "/public/auth/login",
            json={"username": employee.username, "password": employee.password},
        )
        assert response.status_code == 200

    @staticmethod
    async def create_driver(client: AsyncClient, name: str) -> dict[str, Any]:
        response = await client.post(
            "/protected/drivers/create",
            json={"name": name},
        )
        assert response.status_code == 201
        return response.json()["data"]

    @staticmethod
    async def create_product(
        client: AsyncClient,
        name: str,
        base_price: float = 100.0,
    ) -> dict[str, Any]:
        response = await client.post(
            "/protected/products/create",
            json={"name": name, "basePrice": base_price},
        )
        assert response.status_code == 201
        return response.json()["data"]

    @staticmethod
    def point_payload(
        client_id: str,
        product_id: str,
        *,
        quantity: int = 2,
        price: float = 100.0,
    ) -> dict[str, Any]:
        return {
            "clientId": client_id,
            "items": [
                {
                    "productId": product_id,
                    "quantity": quantity,
                    "price": price,
                },
            ],
        }

    @staticmethod
    def delivery_payload(
        driver_id: str,
        car_id: str,
        points: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "plannedDate": date(2025, 3, 15).isoformat(),
            "driverId": driver_id,
            "carId": car_id,
            "startMileage": 100.0,
            "endMileage": 150.0,
            "points": points,
        }

    async def test_create_and_get_delivery_route_sheet(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        client_factory,
        car_factory,
    ) -> None:
        await self.login(client, active_employee)
        client_one = await client_factory(
            name=f"Клиент доставки {uuid7()}",
            phone=unique_phone(),
            address=f"Адрес доставки {uuid7()}",
        )
        client_two = await client_factory(
            name=f"Клиент доставки {uuid7()}",
            phone=unique_phone(),
            address=f"Адрес доставки {uuid7()}",
        )
        car = await car_factory(model="Тестовая машина для доставки")
        driver = await self.create_driver(client, f"Тестовый водитель {uuid7()}")
        product = await self.create_product(
            client,
            unique_product_name("delivery_api"),
            base_price=250.75,
        )
        points = [
            self.point_payload(
                str(client_one.client_id),
                product["productId"],
                quantity=3,
                price=250.75,
            ),
            self.point_payload(
                str(client_two.client_id),
                product["productId"],
                quantity=5,
                price=260.0,
            ),
        ]

        create_response = await client.post(
            f"{DELIVERY_BASE_PATH}/create",
            json=self.delivery_payload(
                driver["driverId"],
                str(car.car_id),
                points,
            ),
        )

        assert create_response.status_code == 201
        created = create_response.json()["data"]
        assert created["plannedDate"] == date(2025, 3, 15).isoformat()
        assert created["isActive"] is True
        assert created["driverId"] == driver["driverId"]
        assert created["carId"] == str(car.car_id)
        assert created["startMileage"] == 100.0
        assert created["endMileage"] == 150.0
        assert [point["position"] for point in created["points"]] == [0, 1]

        get_response = await client.get(
            f"{DELIVERY_BASE_PATH}/{created['deliveryDocumentId']}",
        )
        assert get_response.status_code == 200
        document = get_response.json()["data"]
        assert document["deliveryDocumentId"] == created["deliveryDocumentId"]
        assert [point["clientId"] for point in document["points"]] == [
            str(client_one.client_id),
            str(client_two.client_id),
        ]
        assert [point["clientName"] for point in document["points"]] == [
            client_one.name,
            client_two.name,
        ]
        assert document["points"][0]["address"] == client_one.address
        assert document["points"][0]["items"][0]["productId"] == product["productId"]
        assert document["points"][0]["items"][0]["productName"] == product["name"]
        assert document["points"][0]["items"][0]["quantity"] == 3
        assert document["points"][0]["items"][0]["price"] == 250.75
        assert document["points"][1]["items"][0]["quantity"] == 5
        assert document["points"][1]["items"][0]["price"] == 260.0


    async def test_create_and_get_pickup_sheet(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        client_factory,
    ) -> None:
        await self.login(client, active_employee)
        pickup_client = await client_factory(
            name=f"Клиент самовывоза {uuid7()}",
            phone=unique_phone(),
            address=f"Адрес самовывоза {uuid7()}",
        )
        product = await self.create_product(
            client,
            unique_product_name("pickup_api"),
            base_price=75.25,
        )

        response = await client.post(
            f"{PICKUP_BASE_PATH}/create",
            json={
                "plannedDate": date(2025, 3, 20).isoformat(),
                "points": [
                    self.point_payload(
                        str(pickup_client.client_id),
                        product["productId"],
                        quantity=4,
                        price=75.25,
                    ),
                ],
            },
        )

        assert response.status_code == 201
        created = response.json()["data"]
        assert "driverId" not in created
        assert "carId" not in created
        assert "startMileage" not in created
        assert "endMileage" not in created

        get_response = await client.get(
            f"{PICKUP_BASE_PATH}/{created['deliveryDocumentId']}",
        )
        assert get_response.status_code == 200
        document = get_response.json()["data"]
        assert document["plannedDate"] == date(2025, 3, 20).isoformat()
        assert document["points"][0]["clientName"] == pickup_client.name
        assert document["points"][0]["items"][0]["productName"] == product["name"]
        assert document["points"][0]["items"][0]["quantity"] == 4
        assert document["points"][0]["items"][0]["price"] == 75.25


    async def test_create_validation_errors(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        client_factory,
        car_factory,
    ) -> None:
        await self.login(client, active_employee)
        first_client = await client_factory(
            name=f"Клиент проверки {uuid7()}",
            phone=unique_phone(),
        )
        second_client = await client_factory(
            name=f"Клиент проверки {uuid7()}",
            phone=unique_phone(),
        )
        car = await car_factory()
        driver = await self.create_driver(client, f"Водитель проверки {uuid7()}")
        product = await self.create_product(client, unique_product_name("validation"))

        valid_point = self.point_payload(
            str(first_client.client_id),
            product["productId"],
        )

        no_points = await client.post(
            f"PICKUP_BASE_PATH/create",
            json={
                "plannedDate": date(2025, 3, 15).isoformat(),
                "points": [],
            },
        )
        assert no_points.status_code == 404

        no_points = await client.post(
            f"{PICKUP_BASE_PATH}/create",
            json={
                "plannedDate": date(2025, 3, 15).isoformat(),
                "points": [],
            },
        )
        assert no_points.status_code == 422

        point_without_items = {
            "clientId": str(first_client.client_id),
            "items": [],
        }
        empty_items = await client.post(
            f"{PICKUP_BASE_PATH}/create",
            json={
                "plannedDate": date(2025, 3, 15).isoformat(),
                "points": [point_without_items],
            },
        )
        assert empty_items.status_code == 422

        duplicate_clients = await client.post(
            f"{PICKUP_BASE_PATH}/create",
            json={
                "plannedDate": date(2025, 3, 15).isoformat(),
                "points": [
                    valid_point,
                    self.point_payload(
                        str(first_client.client_id),
                        product["productId"],
                    ),
                ],
            },
        )
        assert duplicate_clients.status_code == 422

        duplicate_products = await client.post(
            f"{PICKUP_BASE_PATH}/create",
            json={
                "plannedDate": date(2025, 3, 15).isoformat(),
                "points": [
                    {
                        "clientId": str(second_client.client_id),
                        "items": [
                            {
                                "productId": product["productId"],
                                "quantity": 1,
                                "price": 10.0,
                            },
                            {
                                "productId": product["productId"],
                                "quantity": 2,
                                "price": 10.0,
                            },
                        ],
                    },
                ],
            },
        )
        assert duplicate_products.status_code == 422

        invalid_mileage = await client.post(
            f"{DELIVERY_BASE_PATH}/create",
            json={
                **self.delivery_payload(
                    driver["driverId"],
                    str(car.car_id),
                    [valid_point],
                ),
                "endMileage": 100.0,
            },
        )
        assert invalid_mileage.status_code == 422

        invalid_pickup_fields = await client.post(
            f"{PICKUP_BASE_PATH}/create",
            json={
                "plannedDate": date(2025, 3, 15).isoformat(),
                "driverId": driver["driverId"],
                "points": [valid_point],
            },
        )
        assert invalid_pickup_fields.status_code == 422


    async def test_patch_validation_errors(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        client_factory,
        car_factory,
    ) -> None:
        await self.login(client, active_employee)
        first_client = await client_factory(
            name=f"PATCH клиент {uuid7()}",
            phone=unique_phone(),
        )
        second_client = await client_factory(
            name=f"PATCH клиент {uuid7()}",
            phone=unique_phone(),
        )
        car = await car_factory()
        driver = await self.create_driver(client, f"PATCH водитель {uuid7()}")
        product = await self.create_product(client, unique_product_name("patch_validation"))
        create_response = await client.post(
            f"{DELIVERY_BASE_PATH}/create",
            json=self.delivery_payload(
                driver["driverId"],
                str(car.car_id),
                [
                    self.point_payload(
                        str(first_client.client_id),
                        product["productId"],
                    ),
                ],
            ),
        )
        assert create_response.status_code == 201
        document_id = create_response.json()["data"]["deliveryDocumentId"]
        point_id = create_response.json()["data"]["points"][0]["pointId"]

        empty_patch = await client.patch(
            f"{DELIVERY_BASE_PATH}/{document_id}",
            json={},
        )
        assert empty_patch.status_code == 422

        null_required_field = await client.patch(
            f"{DELIVERY_BASE_PATH}/{document_id}",
            json={"plannedDate": None},
        )
        assert null_required_field.status_code == 422

        empty_patch_items = await client.patch(
            f"{DELIVERY_BASE_PATH}/{document_id}",
            json={
                "points": [
                    {
                        "pointId": point_id,
                        "clientId": str(first_client.client_id),
                        "items": [],
                    },
                ],
            },
        )
        assert empty_patch_items.status_code == 422

        repeated_point_id = await client.patch(
            f"{DELIVERY_BASE_PATH}/{document_id}",
            json={
                "points": [
                    {
                        "pointId": point_id,
                        "clientId": str(first_client.client_id),
                        "items": [
                            {
                                "productId": product["productId"],
                                "quantity": 1,
                                "price": 100.0,
                            },
                        ],
                    },
                    {
                        "pointId": point_id,
                        "clientId": str(second_client.client_id),
                        "items": [
                            {
                                "productId": product["productId"],
                                "quantity": 1,
                                "price": 100.0,
                            },
                        ],
                    },
                ],
            },
        )
        assert repeated_point_id.status_code == 422


    async def test_patch_replaces_points_and_preserves_them_when_omitted(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        client_factory,
        car_factory,
    ) -> None:
        await self.login(client, active_employee)
        first_client = await client_factory(
            name=f"Первый клиент маршрута {uuid7()}",
            phone=unique_phone(),
        )
        second_client = await client_factory(
            name=f"Второй клиент маршрута {uuid7()}",
            phone=unique_phone(),
        )
        third_client = await client_factory(
            name=f"Третий клиент маршрута {uuid7()}",
            phone=unique_phone(),
        )
        car = await car_factory()
        driver = await self.create_driver(client, f"Водитель маршрута {uuid7()}")
        first_product = await self.create_product(
            client,
            unique_product_name("patch_first"),
        )
        second_product = await self.create_product(
            client,
            unique_product_name("patch_second"),
        )
        create_response = await client.post(
            f"{DELIVERY_BASE_PATH}/create",
            json=self.delivery_payload(
                driver["driverId"],
                str(car.car_id),
                [
                    self.point_payload(
                        str(first_client.client_id),
                        first_product["productId"],
                        quantity=2,
                    ),
                    self.point_payload(
                        str(second_client.client_id),
                        first_product["productId"],
                        quantity=3,
                    ),
                ],
            ),
        )
        assert create_response.status_code == 201
        created = create_response.json()["data"]
        document_id = created["deliveryDocumentId"]
        first_point_id = created["points"][0]["pointId"]
        second_point_id = created["points"][1]["pointId"]

        lock_response = await client.post(
            f"{DELIVERY_BASE_PATH}/{document_id}/edit-lock",
        )
        assert lock_response.status_code == 200

        field_only_patch = await client.patch(
            f"{DELIVERY_BASE_PATH}/{document_id}",
            json={"plannedDate": date(2025, 3, 16).isoformat()},
        )
        assert field_only_patch.status_code == 200
        assert [
            point["clientId"]
            for point in field_only_patch.json()["data"]["points"]
        ] == [
            str(first_client.client_id),
            str(second_client.client_id),
        ]

        replace_points = await client.patch(
            f"{DELIVERY_BASE_PATH}/{document_id}",
            json={
                "points": [
                    {
                        "pointId": second_point_id,
                        "clientId": str(second_client.client_id),
                        "items": [
                            {
                                "productId": second_product["productId"],
                                "quantity": 8,
                                "price": 215.0,
                            },
                        ],
                    },
                    self.point_payload(
                        str(third_client.client_id),
                        first_product["productId"],
                        quantity=4,
                        price=125.0,
                    ),
                ],
            },
        )
        assert replace_points.status_code == 200
        replaced = replace_points.json()["data"]
        assert [point["clientId"] for point in replaced["points"]] == [
            str(second_client.client_id),
            str(third_client.client_id),
        ]
        assert [point["position"] for point in replaced["points"]] == [0, 1]
        assert replaced["points"][0]["pointId"] == second_point_id
        assert replaced["points"][0]["items"] == [
            {
                "productId": second_product["productId"],
                "productName": second_product["name"],
                "quantity": 8,
                "price": 215.0,
            },
        ]
        assert replaced["points"][1]["items"][0]["productId"] == first_product["productId"]
        assert first_point_id not in {point["pointId"] for point in replaced["points"]}

        delete_all_points = await client.patch(
            f"{DELIVERY_BASE_PATH}/{document_id}",
            json={"points": []},
        )
        assert delete_all_points.status_code == 200
        assert delete_all_points.json()["data"]["points"] == []

        unknown_document = await client.patch(
            f"{DELIVERY_BASE_PATH}/{uuid7()}",
            json={"plannedDate": date(2025, 3, 17).isoformat()},
        )
        assert unknown_document.status_code == 404

        foreign_point = await client.patch(
            f"{DELIVERY_BASE_PATH}/{document_id}",
            json={
                "points": [
                    {
                        "pointId": first_point_id,
                        "clientId": str(first_client.client_id),
                        "items": [
                            {
                                "productId": first_product["productId"],
                                "quantity": 1,
                                "price": 100.0,
                            },
                        ],
                    },
                ],
            },
        )
        assert foreign_point.status_code == 422


    async def test_patch_without_lock_is_rejected_by_contract(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        client_factory,
        car_factory,
    ) -> None:
        await self.login(client, active_employee)
        delivery_client = await client_factory(phone=unique_phone())
        car = await car_factory()
        driver = await self.create_driver(client, f"Водитель без блокировки {uuid7()}")
        product = await self.create_product(client, unique_product_name("no_lock"))
        create_response = await client.post(
            f"{DELIVERY_BASE_PATH}/create",
            json=self.delivery_payload(
                driver["driverId"],
                str(car.car_id),
                [
                    self.point_payload(
                        str(delivery_client.client_id),
                        product["productId"],
                    ),
                ],
            ),
        )
        assert create_response.status_code == 201
        document_id = create_response.json()["data"]["deliveryDocumentId"]

        update_response = await client.patch(
            f"{DELIVERY_BASE_PATH}/{document_id}",
            json={"plannedDate": date(2025, 3, 16).isoformat()},
        )

        # Контракт требует действующую блокировку владельца. Текущая реализация
        # use case пока может принять это изменение без блокировки.
        assert update_response.status_code == 409


    async def test_cancel_restore_and_list_filters(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        client_factory,
        car_factory,
    ) -> None:
        await self.login(client, active_employee)
        delivery_client = await client_factory(
            name=f"Клиент отменяемого документа {uuid7()}",
            phone=unique_phone(),
        )
        car = await car_factory()
        driver = await self.create_driver(client, f"Водитель отменяемого {uuid7()}")
        product = await self.create_product(client, unique_product_name("cancel_restore"))
        create_response = await client.post(
            f"{DELIVERY_BASE_PATH}/create",
            json=self.delivery_payload(
                driver["driverId"],
                str(car.car_id),
                [
                    self.point_payload(
                        str(delivery_client.client_id),
                        product["productId"],
                        quantity=6,
                        price=130.0,
                    ),
                ],
            ),
        )
        assert create_response.status_code == 201
        created = create_response.json()["data"]
        document_id = created["deliveryDocumentId"]

        cancel_response = await client.post(
            f"{DELIVERY_BASE_PATH}/{document_id}/cancel",
        )
        assert cancel_response.status_code == 200
        assert cancel_response.json()["data"]["isActive"] is False

        active_list = await client.get(
            DELIVERY_BASE_PATH,
            params={"include_cancelled": False},
        )
        assert active_list.status_code == 200
        active_ids = {
            item["deliveryDocumentId"]
            for item in active_list.json()["data"]["deliveryRouteSheets"]
        }
        assert document_id not in active_ids

        all_list = await client.get(
            DELIVERY_BASE_PATH,
            params={"include_cancelled": True},
        )
        assert all_list.status_code == 200
        all_ids = {
            item["deliveryDocumentId"]
            for item in all_list.json()["data"]["deliveryRouteSheets"]
        }
        assert document_id in all_ids

        restore_response = await client.post(
            f"{DELIVERY_BASE_PATH}/{document_id}/restore",
        )
        assert restore_response.status_code == 200
        restored = restore_response.json()["data"]
        assert restored["isActive"] is True
        assert len(restored["points"]) == 1
        assert restored["points"][0]["clientId"] == str(delivery_client.client_id)
        assert restored["points"][0]["items"][0]["productId"] == product["productId"]
        assert restored["points"][0]["items"][0]["quantity"] == 6
        assert restored["points"][0]["items"][0]["price"] == 130.0


    async def test_edit_lock_acquire_renew_release_and_other_owner_restrictions(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        employee_factory,
        client_factory,
        car_factory,
    ) -> None:
        await self.login(client, active_employee)
        delivery_client = await client_factory(phone=unique_phone())
        car = await car_factory()
        driver = await self.create_driver(client, f"Водитель блокировки {uuid7()}")
        product = await self.create_product(client, unique_product_name("edit_lock"))
        create_response = await client.post(
            f"{DELIVERY_BASE_PATH}/create",
            json=self.delivery_payload(
                driver["driverId"],
                str(car.car_id),
                [
                    self.point_payload(
                        str(delivery_client.client_id),
                        product["productId"],
                    ),
                ],
            ),
        )
        assert create_response.status_code == 201
        document_id = create_response.json()["data"]["deliveryDocumentId"]

        acquire_response = await client.post(
            f"{DELIVERY_BASE_PATH}/{document_id}/edit-lock",
        )
        assert acquire_response.status_code == 200
        assert acquire_response.json()["data"]["ownerName"] == active_employee.username

        other_employee = await employee_factory()
        await self.login(client, other_employee)

        second_acquire = await client.post(
            f"{DELIVERY_BASE_PATH}/{document_id}/edit-lock",
        )
        assert second_acquire.status_code == 409

        foreign_renew = await client.patch(
            f"{DELIVERY_BASE_PATH}/{document_id}/edit-lock",
        )
        assert foreign_renew.status_code in {403, 404, 409}

        foreign_release = await client.delete(
            f"{DELIVERY_BASE_PATH}/{document_id}/edit-lock",
        )
        assert foreign_release.status_code in {403, 404, 409}

        await self.login(client, active_employee)
        renew_response = await client.patch(
            f"{DELIVERY_BASE_PATH}/{document_id}/edit-lock",
        )
        assert renew_response.status_code == 200
        assert renew_response.json()["data"]["ownerName"] == active_employee.username

        release_response = await client.delete(
            f"{DELIVERY_BASE_PATH}/{document_id}/edit-lock",
        )
        assert release_response.status_code == 200

        missing_renew = await client.patch(
            f"{DELIVERY_BASE_PATH}/{document_id}/edit-lock",
        )
        assert missing_renew.status_code == 404


    async def test_delivery_document_routes_require_authentication(
        self,
        client: AsyncClient,
    ) -> None:
        delivery_response = await client.get(DELIVERY_BASE_PATH)
        pickup_response = await client.get(PICKUP_BASE_PATH)

        assert delivery_response.status_code == 401
        assert pickup_response.status_code == 401
