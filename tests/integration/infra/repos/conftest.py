import os
from collections.abc import Generator

import pytest

from src.core.paths import PROJECT_DIR
from tests.integration.db_helpers import bootstrap_test_database

# Импортируем наш хелпер (укажите ваш правильный путь)

ALEMBIC_CONFIG = PROJECT_DIR / "src" / "common" / "infra" / "db" / "postgres" / "alembic" / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def prepare_repository_database() -> Generator[None]:
    """Готовит изолированную базу данных специально для тестов репозиториев."""
    # Берем имя из POSTGRES_REPO_TEST_DB или задаем дефолт
    repo_db_name = os.environ.get("POSTGRES_REPO_TEST_DB", "mountain_fairytale_repo_test")

    bootstrap_test_database(test_db_name=repo_db_name, alembic_config_path=ALEMBIC_CONFIG, project_dir=PROJECT_DIR)
    yield
