# Mountain Fairytale backend

FastAPI API локального Windows-приложения для службы доставки воды.
Python 3.13, PostgreSQL, SQLAlchemy, Alembic, Poetry.

- [Первичная установка Ubuntu VM и запуск Docker Compose](docs/operations/first-install.md).
- [Контракт эксплуатации и выпусков](docs/contracts/operations-deployment-updates.md).
- [План внедрения](docs/contracts/operations-implementation-plan.md).

## Разработка

```powershell
poetry install --no-root
poetry run python -m src.main
```

Параметры разработки берутся из локального `.env`. Серверное окружение
создаётся отдельно; шаблон — `deploy/.env.example`. Секреты не коммитятся.

## Проверки

```powershell
poetry check --lock
poetry run pytest
```

Интеграционные тесты пересоздают схему **тестовых** PostgreSQL-баз, применяют
миграции и требуют правильного окружения. Никогда не направляйте их на рабочую БД.
CI использует отдельный временный PostgreSQL и не имеет доступа к production.

В исходном проекте есть накопленные замечания Ruff. До отдельной задачи их
исправления CI проверяет Ruff для добавленных/изменённых Python-файлов целиком;
правила из `pyproject.toml` не ослабляются. Полный отчёт:

```powershell
poetry run ruff check src tests scripts
```
