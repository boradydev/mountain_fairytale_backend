import argparse
from pathlib import Path


def move_migrations(
    versions_dir: Path,
    create_sql_files: bool,
) -> None:
    """
    Ищет в директории versions файлы миграций (*.py).

    Для каждого файла:
    - создаёт папку с именем файла без расширения;
    - переносит файл внутрь этой папки;
    - при необходимости создаёт update.sql и downgrade.sql.

    Пример:

    versions/
    └── 001_initial.py

    Станет:

    versions/
    └── 001_initial/
        ├── downgrade.sql
        ├── migration.py
        └── update.sql
    """
    if not versions_dir.exists():
        raise FileNotFoundError(f"Migration directory not found: {versions_dir}.")

    count = 0
    for migration_file in versions_dir.glob("*.py"):
        migration_dir = versions_dir / migration_file.stem
        migration_dir.mkdir(exist_ok=True)

        migration_file.rename(migration_dir / "migration.py")

        if create_sql_files:
            (migration_dir / "upgrade.sql").touch(exist_ok=True)
            (migration_dir / "downgrade.sql").touch(exist_ok=True)

        print(f"Migration packed: {migration_file.stem}.")
        count += 1

    if count == 0:
        print("Migrations not found.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Скрипт для автоматической изоляции миграций Alembic в подпапки."
    )

    parser.add_argument(
        "--sql",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Создавать ли пустые .sql файлы рядом с миграцией (по умолчанию: нет)",
    )

    args = parser.parse_args()

    current_script_dir = Path(__file__).resolve().parent
    versions_dir = current_script_dir / "versions"

    move_migrations(
        versions_dir=versions_dir,
        create_sql_files=args.sql,
    )


if __name__ == "__main__":
    main()
