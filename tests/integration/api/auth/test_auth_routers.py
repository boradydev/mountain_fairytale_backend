from httpx import AsyncClient
from uuid6 import uuid7

from tests.integration.conftest import EmployeeTestData


BASE_PATH = "/public/auth"


class TestAuthFlow:
    """Интеграционные тесты API авторизации.

    Используется реальный PostgreSQL, реальный UOW, реальные сервисы паролей
    и JWT. HTTP-запросы выполняются асинхронным httpx.AsyncClient.

    При генерации или обновлении тестов в этом модуле
    СТРОГО ЗАПРЕЩЕНО писать проверки (assert) на поле "detail", так как
    его структура может динамически меняться.
    """

    @staticmethod
    async def login(
        client: AsyncClient,
        employee: EmployeeTestData,
        *,
        password: str | None = None,
    ):
        return await client.post(
            f"{BASE_PATH}/login",
            json={
                "username": employee.username,
                "password": employee.password if password is None else password,
            },
        )

    async def test_login_success(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        response = await self.login(client, active_employee)

        assert response.status_code == 200

        data = response.json()["data"]

        assert "accessToken" in data
        assert "refreshToken" in data
        assert client.cookies.get("access-token") == data["accessToken"]
        assert client.cookies.get("refresh-token") == data["refreshToken"]

    async def test_login_invalid_credentials(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        response = await self.login(
            client,
            active_employee,
            password="wrong_password",
        )

        assert response.status_code == 401

    async def test_login_employee_not_found(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            f"{BASE_PATH}/login",
            json={
                "username": f"missing_{uuid7()}",
                "password": "any_password",
            },
        )

        assert response.status_code == 401

    async def test_login_employee_deactivated(
        self,
        client: AsyncClient,
        inactive_employee: EmployeeTestData,
    ) -> None:
        response = await self.login(client, inactive_employee)

        assert response.status_code == 403

    async def test_login_validation_error_too_long(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            f"{BASE_PATH}/login",
            json={
                "username": "a" * 51,
                "password": "password123",
            },
        )

        assert response.status_code == 422

    async def test_refresh_success(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        login_response = await self.login(client, active_employee)
        assert login_response.status_code == 200

        refresh_token = login_response.json()["data"]["refreshToken"]

        response = await client.post(
            f"{BASE_PATH}/refresh",
            json={"refreshToken": refresh_token},
        )

        assert response.status_code == 200

        data = response.json()["data"]

        assert "accessToken" in data
        assert "refreshToken" in data
        assert client.cookies.get("access-token") == data["accessToken"]
        assert client.cookies.get("refresh-token") == data["refreshToken"]

    async def test_refresh_via_cookies_success(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
    ) -> None:
        login_response = await self.login(client, active_employee)
        assert login_response.status_code == 200

        response = await client.post(
            f"{BASE_PATH}/refresh",
            json={"refreshToken": None},
        )

        assert response.status_code == 200

        data = response.json()["data"]

        assert "accessToken" in data
        assert client.cookies.get("access-token") == data["accessToken"]
        assert client.cookies.get("refresh-token") == data["refreshToken"]

    async def test_refresh_no_token_provided(
        self,
        client: AsyncClient,
    ) -> None:
        client.cookies.clear()

        response = await client.post(
            f"{BASE_PATH}/refresh",
            json={"refreshToken": None},
        )

        assert response.status_code == 401

    async def test_refresh_invalid_token(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            f"{BASE_PATH}/refresh",
            json={"refreshToken": "not.a.valid.jwt.token"},
        )

        assert response.status_code == 401

    async def test_refresh_expired_token(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        token_service_factory,
    ) -> None:
        expired_token_service = token_service_factory(
            refresh_expire=-1,
        )

        expired_token = expired_token_service.create_refresh_token(
            employee_id=str(active_employee.employee_id),
        )

        response = await client.post(
            f"{BASE_PATH}/refresh",
            json={"refreshToken": expired_token},
        )

        assert response.status_code == 401

    async def test_refresh_employee_deactivated(
        self,
        client: AsyncClient,
        active_employee: EmployeeTestData,
        employees_uow_factory,
    ) -> None:
        login_response = await self.login(client, active_employee)
        assert login_response.status_code == 200

        refresh_token = login_response.json()["data"]["refreshToken"]

        async with employees_uow_factory() as uow:
            employee = await uow.employees.get_by_id(
                active_employee.employee_id,
            )
            assert employee is not None

            employee.deactivate(
                actor_id=active_employee.employee_id,
            )

            await uow.employees.update(employee)
            await uow.commit(events=employee.pull_events())

        response = await client.post(
            f"{BASE_PATH}/refresh",
            json={"refreshToken": refresh_token},
        )

        assert response.status_code == 403
