# Mountain Fairytale backend

FastAPI API локального Windows-приложения для службы доставки воды.
Python 3.13, PostgreSQL, SQLAlchemy, Alembic, Poetry.

- Начните с [первой установки с нуля](docs/operations/first-install.md): чистая
  Ubuntu VM → готовый образ GHCR → новая БД/API → S3 → доставка обновлений.
- [Навигация по эксплуатации](docs/operations/README.md): установка,
  настройки, backup/restore, обновление и типовые неполадки.
- [Все серверные ENV и применение изменений](docs/operations/server-env.md).
- [Резервные копии PostgreSQL в Timeweb S3](docs/operations/backups.md).
- [Пробное восстановление и перенос на новую VM](docs/operations/restore.md).
- [Разрешение деплоя в GitHub, установка на VM и откат](docs/operations/backend-deploy.md).
- [Обслуживание, остановка/запуск и диагностика](docs/operations/maintenance.md).
- [GlitchTip, SDK, проверка диска/бэкапов и активация мониторинга](docs/operations/monitoring.md).
- [Контракт эксплуатации и выпусков](docs/contracts/operations-deployment-updates.md).
- [План внедрения](docs/contracts/operations-implementation-plan.md).
- [Совместимость Flutter и API](docs/contracts/client-api-compatibility-plan.md)
- **[Восстановление доступа администратора: узнать логин и сменить забытый пароль](docs/operations/admin-access.md).**
  — проверка версии клиента, требование обновления и правила выпуска.

## Разработка

```powershell
poetry install --no-root
poetry run python -m src.main
```

Параметры разработки берутся из локального `.env`; шаблон для нового окружения —
[.env.example](.env.example). При обновлении существующего `.env` сохраните свои
пароли, JWT-секрет и ключ Geoapify. Сам `.env` исключён из Git.

| Переменная | Назначение | Локальное значение |
| --- | --- | --- |
| `POSTGRES_DB` | Ручной запуск приложения; данные сохраняются | `mountain_fairytale_sales_live_20261101` |
| `POSTGRES_API_TEST_DB` | API-тесты | `mountain_fairytale_api_test` |
| `POSTGRES_REPO_TEST_DB` | Тесты репозиториев | `mountain_fairytale_repo_test` |

Адрес, порт и учётные данные локального PostgreSQL общие. Базы должны существовать
до первого запуска. Достаточно выбрать нужный набор тестов: pytest автоматически
подставляет его базу для подключения и миграций; менять `POSTGRES_DB` вручную
для тестов не нужно. Подготовка тестов пересоздаёт только тестовую схему.
Имена тестовых баз должны заканчиваться на `_test`; helper откажется очищать
базу ручного запуска.

В шаблоне также указаны настройки авторизации, необязательного Geoapify/cache
и отключённого локального мониторинга (`SENTRY_ENVIRONMENT=development`).
Для запуска из корня проекта:

```powershell
poetry run python -m alembic -c src/common/infra/db/postgres/alembic/alembic.ini current
# Применять новые миграции к базе ручного запуска после проверки изменений:
poetry run python -m alembic -c src/common/infra/db/postgres/alembic/alembic.ini upgrade head
poetry run python -m src.main
```

Уже работающий процесс нужно перезапустить, чтобы он прочитал обновлённый `.env`.
Серверное окружение создаётся отдельно; шаблон — `deploy/.env.example`.
Параметры Docker, backup и VPN в локальный `.env` для запуска Python не требуются.

## Проверки

```powershell
poetry check --lock
poetry run pytest
```

Отдельный запуск API и репозиториев использует соответствующие переменные `.env`:

```powershell
poetry run pytest tests/integration/api
poetry run pytest tests/integration/infra/repos
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
