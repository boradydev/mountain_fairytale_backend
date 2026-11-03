import os
import re
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

from src.common.infra.db.postgres.settings import PostgresSettings


def validate_test_database_name(test_db_name: str) -> None:
    """Refuse schema recreation outside explicitly named test databases."""
    if re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*_test", test_db_name) is None:
        raise ValueError("Test database name must be a PostgreSQL identifier ending in _test.")


def bootstrap_test_database(test_db_name: str, alembic_config_path: Path, project_dir: Path) -> None:
    """Recreate a test schema and migrate it without changing the runtime database."""
    validate_test_database_name(test_db_name)
    settings = PostgresSettings(POSTGRES_DB=test_db_name)
    sync_engine = create_engine(url=settings.DB_URL_SYNC, isolation_level="AUTOCOMMIT")

    try:
        # Check the selected database and Cyrillic locale before recreating its schema.
        with sync_engine.connect() as connection:
            actual_db = connection.execute(text("SELECT current_database()")).scalar_one()
            if actual_db != test_db_name:
                raise RuntimeError("Test connection targets an unexpected database; schema recreation refused.")
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

    finally:
        sync_engine.dispose()

    # Alembic receives a separate process environment; the caller retains its DB.
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(alembic_config_path), "upgrade", "head"],
        cwd=project_dir,
        env={**os.environ, "POSTGRES_DB": test_db_name},
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
