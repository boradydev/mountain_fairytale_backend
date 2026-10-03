from tests.integration.api.conftest import client


class TestAuthFlow:
    # --- Сценарии для /login ---

    def test_login_success(self, client, admin_settings):
        """Позитивный сценарий: верные данные админа -> 200 OK + токены."""
        # Используем данные из фикстуры AdminSettings
        payload = {
            "username": admin_settings.ADMIN_USERNAME,
            "password": admin_settings.ADMIN_PASSWORD,
        }
        response = client.post("/public/auth/login", json=payload)

        assert response.status_code == 200
        data = response.json()["data"]

        # Body cemalCase
        assert "accessToken" in data
        assert "refreshToken" in data

        # Cookies kebab-case
        assert "access-token" in client.cookies
        assert "refresh-token" in client.cookies

    def test_login_invalid_credentials(self):
        """Неверный пароль/логин -> 401."""
        payload = {"username": "wrong_user", "password": "wrong_password"}
        response = client.post("/public/auth/login", json=payload)

        assert response.status_code == 401

    def test_login_employee_not_found(self):
        """Пользователь не существует -> 404."""
        payload = {"username": "non_existent", "password": "any_password"}
        response = client.post("/public/auth/login", json=payload)

        assert response.status_code == 404

    def test_login_employee_deactivated(self):
        """Пользователь деактивирован -> 403."""
        payload = {"username": "deactivated_user", "password": "password123"}
        response = client.post("/public/auth/login", json=payload)

        assert response.status_code == 403

        # --- Сценарии для /refresh ---

    def test_refresh_success(self):
        """Обновление токена с валидным refresh_token -> 200 OK."""
        payload = {"refresh_token": "valid_refresh_token"}
        response = client.post("/public/auth/refresh", json=payload)

        assert response.status_code == 200
        assert "access_token" in response.json()["data"]

    def test_refresh_no_token_provided(self):
        """Токен не передан ни в теле, ни в куках -> 401."""
        client.cookies.clear()
        payload = {"refresh_token": None}
        response = client.post("/public/auth/refresh", json=payload)

        assert response.status_code == 401

    def test_refresh_employee_not_found(self):
        """Токен есть, но пользователь удален из системы -> 404."""
        payload = {"refresh_token": "token_for_deleted_user"}
        response = client.post("/public/auth/refresh", json=payload)

        assert response.status_code == 404
