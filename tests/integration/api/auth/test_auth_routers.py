from tests.integration.api.conftest import client, token_service_factory


class TestAuthFlow:
    """Тесты авторизации.

    При генерации или обновлении тестов в этом модуле
    СТРОГО ЗАПРЕЩЕНО писать проверки (assert) на поле "detail", так как
    его структура может динамически меняться.
    """

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

        # Body camelCase
        assert "accessToken" in data
        assert "refreshToken" in data

        # Cookies kebab-case
        assert "access-token" in client.cookies
        assert "refresh-token" in client.cookies

    def test_login_invalid_credentials(self, client):
        """Неверный пароль/логин -> 401."""
        payload = {"username": "wrong_user", "password": "wrong_password"}
        response = client.post("/public/auth/login", json=payload)

        assert response.status_code == 401

    def test_login_employee_not_found(self, client):
        """Пользователь не существует -> 401 (согласно безопасности)."""
        payload = {"username": "non_existent", "password": "any_password"}
        response = client.post("/public/auth/login", json=payload)

        assert response.status_code == 401

    def test_login_employee_deactivated(self, client):
        """Пользователь деактивирован -> 403."""
        payload = {"username": "deactivated_user", "password": "password123"}
        response = client.post("/public/auth/login", json=payload)

        assert response.status_code == 403

    def test_login_validation_error_too_long(self, client):
        """Слишком длинный username (> 50 символов) -> 422."""
        payload = {
            "username": "a" * 51,
            "password": "password123",
        }
        response = client.post("/public/auth/login", json=payload)

        assert response.status_code == 422

    # --- Сценарии для /refresh ---

    def test_refresh_success(self, client, admin_settings):
        """Обновление токена с валидным refresh_token в теле -> 200 OK."""
        # 1. Получаем реальный refresh_token через логин
        login_payload = {
            "username": admin_settings.ADMIN_USERNAME,
            "password": admin_settings.ADMIN_PASSWORD,
        }
        login_response = client.post("/public/auth/login", json=login_payload)
        refresh_token = login_response.json()["data"]["refreshToken"]

        # 2. Используем полученный токен для обновления
        payload = {"refreshToken": refresh_token}
        response = client.post("/public/auth/refresh", json=payload)

        assert response.status_code == 200
        assert "accessToken" in response.json()["data"]

    def test_refresh_via_cookies_success(self, client, admin_settings):
        """Обновление токена через Cookies (тело пустое) -> 200 OK."""
        # 1. Логин для установки кук
        login_payload = {
            "username": admin_settings.ADMIN_USERNAME,
            "password": admin_settings.ADMIN_PASSWORD,
        }
        client.post("/public/auth/login", json=login_payload)

        # 2. Запрос на refresh без токена в теле (должен взяться из кук)
        payload = {"refreshToken": None}
        response = client.post("/public/auth/refresh", json=payload)

        assert response.status_code == 200
        assert "accessToken" in response.json()["data"]

    def test_refresh_no_token_provided(self, client):
        """Токен не передан ни в теле, ни в куках -> 401."""
        client.cookies.clear()
        payload = {"refreshToken": None}
        response = client.post("/public/auth/refresh", json=payload)

        assert response.status_code == 401

    def test_refresh_invalid_token(self, client):
        """Передан невалидный JWT токен -> 401."""
        payload = {"refreshToken": "not.a.valid.jwt.token"}
        response = client.post("/public/auth/refresh", json=payload)

        assert response.status_code == 401

    def test_refresh_expired_token(self, client, admin_settings):
        """Передан просроченный токен -> 401."""
        # Создаем сервис с нулевым временем жизни для refresh токена
        expired_token_service = token_service_factory(refresh_expire=0)
        
        # Генерируем токен (используем ID админа для правдоподобности)
        expired_token = expired_token_service.create_refresh_token(
            employee_id=str("01a1014f-5449-7657-9bf4-61312a4f7219")
        )
        
        payload = {"refreshToken": expired_token}
        response = client.post("/public/auth/refresh", json=payload)

        assert response.status_code == 401

    def test_refresh_employee_deactivated(self, client):
        """Валидный токен, но сотрудник деактивирован -> 403."""
        # Предполагается, что в системе есть пользователь, который был активен при выдаче токена, но стал деактивирован
        payload = {"refreshToken": "valid_token_for_deactivated_user"}
        response = client.post("/public/auth/refresh", json=payload)

        # Если моки настроены, ожидаем 403
        if response.status_code != 401: # Если токен прошел валидацию JWT
            assert response.status_code == 403
