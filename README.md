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
  — проверка версии клиента, требование обновления и правила выпуска.

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
