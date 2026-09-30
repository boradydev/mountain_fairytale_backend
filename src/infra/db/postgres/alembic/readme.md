## Создание миграции
#### Команда запускается из корня проекта. Необходимо явно указать путь к файлу ``alembic.ini.``
```bash
poetry run alembic -c src/infrastructure/db/postgres/alembic.ini revision
```
## Подготовка миграций к публикации
#### Упаковывает миграции в отдельную папку.
    versions/
    └── 001_initial/
        └── migration.py
#### Параметр --sql дополнительно генерирует файлы:
    versions/
    └── 001_initial/
        ├── downgrade.sql
        ├── migration.py
        └── update.sql
```bash
poetry run python src/infrastructure/db/postgres/alembic/migrations/move_migrations.py --sql
```

## Выполнение SQL-файлов
#### Функция ``sql_reader()`` предназначена для чтения SQL-файлов и выполнения в ``op.execute()``.
#### Используется в случаях, когда миграцию удобнее писать на чистом SQL, а не через API Alembic.
Пример:
```text
op.execute(sql_reader("upgrade.sql"))
```
