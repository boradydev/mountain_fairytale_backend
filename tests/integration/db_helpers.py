import os
import subprocess
import sys
from sqlalchemy import create_engine, text
from pathlib import Path
from src.common.infra.db.postgres.settings import PostgresSettings


def bootstrap_test_database(test_db_name: str, alembic_config_path: Path, project_dir: Path) -> None:
    """
    Универсальная функция для подготовки тестовой БД.
    Проверяет локаль триграмм, сносит схему и накатывает миграции для указанной БД.
    """
    # Сохраняем оригинальное значение, чтобы восстановить в конце
    old_postgres_db = os.environ.get("POSTGRES_DB")

    # 1. Подменяем имя БД в окружении, чтобы PostgresSettings прочитал именно её
    os.environ["POSTGRES_DB"] = test_db_name

    try:
        # Инициализируем настройки (они подтянут уже измененный POSTGRES_DB)
        settings = PostgresSettings()

        # 2. Создаем временный синхронный движок с AUTOCOMMIT
        sync_engine = create_engine(url=settings.DB_URL_SYNC, isolation_level="AUTOCOMMIT")

        # 3. Блокируем поток, сносим старую схему и ПРОВЕРЯЕМ ЛОКАЛЬ СУБД
        with sync_engine.connect() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
            trigrams = connection.execute(text("SELECT show_trgm('Тест');")).scalar()

            db_info = connection.execute(
                text("SELECT datcollate, datctype FROM pg_database WHERE datname = current_database();")
            ).one()

            if not trigrams or len(trigrams) == 0:
                error_message = (
                    f"\n\n[CRITICAL ERROR] "
                    f"База данных '{test_db_name}' имеет несовместимую локаль для нечеткого поиска по кириллице!\n"
                    f"Текущая локаль базы: Collate={db_info.datcollate}, Ctype={db_info.datctype}\n"
                    f"Результат разбиения слова 'Тест' на триграммы: {trigrams}\n"
                    f"ТРЕБУЕТСЯ: Инициализировать Postgres с локалью UTF-8 (например, C.UTF-8 или ru_RU.UTF-8).\n"
                )
                raise RuntimeError(error_message)

            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE;"))
            connection.execute(text("CREATE SCHEMA public;"))

        sync_engine.dispose()

        # 4. Накатываем миграции через Alembic
        subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                str(alembic_config_path),
                "upgrade",
                "head",
            ],
            cwd=project_dir,
            env=os.environ.copy(),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    finally:
        # Возвращаем старую переменную на место, чтобы не ломать глобальный env сессии
        if old_postgres_db is not None:
            os.environ["POSTGRES_DB"] = old_postgres_db
        else:
            os.environ.pop("POSTGRES_DB", None)
