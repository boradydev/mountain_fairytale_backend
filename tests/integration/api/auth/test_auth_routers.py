from fastapi.testclient import TestClient

from src.api.fastapi.app import fastapi_app


client = TestClient(fastapi_app)


class TestAuthFlow:
    # --- Сценарии для /login ---

    def test_login_success(self):
        """Позитивный сценарий: верные данные -> 200 OK + токены."""
        payload = {"username": "admin", "password": "11"}
        response = client.post("/auth/login", json=payload)

        assert response.status_code == 200
        data = response.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        # Проверяем, что установились куки
        assert "access_token" in client.cookies
        assert "refresh_token" in client.cookies

    def test_login_invalid_credentials(self):
        """Неверный пароль/логин -> 401 Invalid credentials."""
        payload = {"username": "wrong_user", "password": "wrong_password"}
        response = client.post("/auth/login", json=payload)

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    def test_login_employee_not_found(self):
        """Пользователь не существует -> 404 Employee not found."""
        payload = {"username": "non_existent", "password": "any_password"}
        response = client.post("/auth/login", json=payload)

        assert response.status_code == 404
        assert response.json()["detail"] == "Employee not found"

    def test_login_employee_deactivated(self):
        """Пользователь деактивирован -> 403 (после правки карты)."""
        payload = {"username": "deactivated_user", "password": "password123"}
        response = client.post("/auth/login", json=payload)

        assert response.status_code == 403
        assert response.json()["detail"] == "Employee account is deactivated"

        # --- Сценарии для /refresh ---

    def test_refresh_success(self):
        """Обновление токена с валидным refresh_token -> 200 OK."""
        payload = {"refresh_token": "valid_refresh_token"}
        response = client.post("/auth/refresh", json=payload)

        assert response.status_code == 200
        assert "access_token" in response.json()["data"]

    def test_refresh_no_token_provided(self):
        """Токен не передан ни в теле, ни в куках -> 401 Refresh token not found."""
        # Очищаем куки перед запросом
        client.cookies.clear()
        payload = {"refresh_token": None}
        response = client.post("/auth/refresh", json=payload)

        assert response.status_code == 401
        assert response.json()["detail"] == "Refresh token not found"

    def test_refresh_employee_not_found(self):
        """Токен есть, но пользователь удален из системы -> 404."""
        payload = {"refresh_token": "token_for_deleted_user"}
        response = client.post("/auth/refresh", json=payload)

        assert response.status_code == 404
        assert response.json()["detail"] == "Employee not found"
