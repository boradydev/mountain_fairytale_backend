import pytest

from src.infra.bootstrap.admins.settings import AdminSettings

@pytest.fixture
def admin_settings() -> AdminSettings:
    return AdminSettings()