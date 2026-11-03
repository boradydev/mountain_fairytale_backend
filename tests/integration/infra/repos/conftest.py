import os

import pytest

from src.core.paths import PROJECT_DIR
from tests.integration.db_helpers import bootstrap_test_database


ALEMBIC_CONFIG = PROJECT_DIR / "src" / "common" / "infra" / "db" / "postgres" / "alembic" / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def prepare_repository_database() -> str:
    """Готовит изолированную базу данных специально для тестов репозиториев."""
    # Берем имя из POSTGRES_REPO_TEST_DB или задаем дефолт
    repo_db_name = os.environ.get("POSTGRES_REPO_TEST_DB", "mountain_fairytale_repo_test")

    bootstrap_test_database(test_db_name=repo_db_name, alembic_config_path=ALEMBIC_CONFIG, project_dir=PROJECT_DIR)
    return repo_db_name


@pytest.fixture
def test_database_name(prepare_repository_database: str) -> str:
    """Name of the database used throughout the current repository test."""
    return prepare_repository_database
