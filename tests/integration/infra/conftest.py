import os
import subprocess
import sys
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text

from src.common.infra.db.postgres.settings import PostgresSettings
from src.core.paths import PROJECT_DIR


"""
Создаем базы данных в windows через базовый шаблон template0, с нужной локалью.

CREATE DATABASE mountain_fairytale_test
    WITH
    TEMPLATE = template0
    ENCODING = 'UTF8'
    LC_COLLATE = 'Russian_Russia.utf8'
    LC_CTYPE = 'Russian_Russia.utf8';
"""


ALEMBIC_CONFIG = PROJECT_DIR / "src" / "common" / "infra" / "db" / "postgres" / "alembic" / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def prepare_repository_database() -> Generator[None]:
    """
    Выполняется строго ОДИН РАЗ на всю сессию тестов.
    Полностью синхронно блокирует поток, пересоздает схему и накатывает миграции.
    """
    # 1. Принудительно выставляем тестовую БД в окружение перед чтением настроек
    test_database = os.environ["POSTGRES_TEST_DB"]
    os.environ["POSTGRES_DB"] = test_database

    # Инициализируем настройки (они подтянут уже измененный POSTGRES_DB)
    settings = PostgresSettings()

    # 2. Создаем временный синхронный движок (использует ваш DB_URL_SYNC)
    # Изолируем его через isolation_level="AUTOCOMMIT", чтобы DROP SCHEMA выполнился без транзакций
    sync_engine = create_engine(url=settings.DB_URL_SYNC, isolation_level="AUTOCOMMIT")

    # 3. Блокируем поток, сносим старую схему и ПРОВЕРЯЕМ ЛОКАЛЬ СУБД
    with sync_engine.connect() as connection:
        # Гарантируем наличие pg_trgm для проверки
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))

        # Проверяем, как база данных разбивает кириллицу на триграммы
        trigrams = connection.execute(text("SELECT show_trgm('Тест');")).scalar()

        # Получаем параметры кодировки и локали текущей базы данных
        db_info = connection.execute(
            text("SELECT datcollate, datctype FROM pg_database WHERE datname = current_database();")
        ).one()

        # Если триграммы пустые (локаль C), взрываем сессию с понятным описанием
        if not trigrams or len(trigrams) == 0:
            error_message = (
                f"\n\n[CRITICAL ERROR] "
                f"База данных '{test_database}' имеет несовместимую локаль для нечеткого поиска по кириллице!\n"
                f"Текущая локаль базы: Collate={db_info.datcollate}, Ctype={db_info.datctype}\n"
                f"Результат разбиения слова 'Тест' на триграммы: {trigrams}\n"
                f"ТРЕБУЕТСЯ: Инициализировать Postgres с локалью UTF-8 (например, C.UTF-8 или ru_RU.UTF-8).\n"
            )
            # Принудительно уничтожаем движок перед выходом, чтобы не вешать соединения
            sync_engine.dispose()
            raise RuntimeError(error_message)

        # Если локаль правильная, продолжаем стандартную подготовку
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE;"))
        connection.execute(text("CREATE SCHEMA public;"))

    # Уничтожаем синхронный движок, чтобы он не держал соединений
    sync_engine.dispose()

    # 4. В том же синхронном потоке накатываем миграции через Alembic
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(ALEMBIC_CONFIG),
            "upgrade",
            "head",
        ],
        cwd=PROJECT_DIR,
        env=os.environ.copy(),
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # База готова, миграции накатаны. Отдаем управление тестам
    yield

    # После окончания ВСЕХ тестов возвращаем исходное имя БД в env (если нужно)
    current_database = os.environ.get("POSTGRES_DB")
    if current_database == test_database:
        os.environ.pop("POSTGRES_DB", None)
