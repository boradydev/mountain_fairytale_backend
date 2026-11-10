# Этап 5, блок 1 — подготовка инфраструктуры

Дата: 10.11.2026. Ветка: `codex/delivery-history`.
Статус этапа 5: **В работе**, не завершён.

Подготовлены отдельное нагрузочное окружение, HTTP-генератор main/high,
инкрементальный журнал восстановления, независимая сверка Decimal/SQL/API,
полная проверка страниц истории, последовательные и ограниченно параллельные
HTTP-измерения. [Команды, архитектура и Flutter QA-029](../stages/05-resilience-load.md).

## Проверки

- `pytest tests/qa tests/unit --basetemp=.codex-tmp\pytest` через локальный
  `.venv\Scripts\python.exe`, TEMP/TMP внутри `.codex-tmp`: **236 passed,
  16 skipped**. Интеграционные тесты создания временных PostgreSQL-баз
  намеренно отключены (`QA_INFRA_LIVE=0`). Предупреждение зависимости anyio
  и ResourceWarning существующего SQLite-теста не вызвали падений.
- После добавления двух дополнительных проверок восстановления POST документа
  и порядка при равных датах/времени: `pytest tests/qa/test_load_tools.py
  --basetemp=.codex-tmp\pytest --no-cov`: **48 passed**.
- Ruff check/format изменённых Python-файлов, `git diff --check`, Python
  `--help` и PowerShell `-Help`: успешно.
- Отказы проверены по фактическим поддельным соединениям: имя production/QA/
  pytest/неизвестное, роль и session_user, endpoint, привилегии/владелец,
  отсутствующий/неверный/доступный для записи маркер. Настоящий entrypoint
  Alembic запускался с поддельным engine: переход не вызывается при отказе,
  offline/no-flag/комбинация QA+load запрещены.
- Проверены детерминированные планы обоих профилей, количества/диапазоны,
  совместимость payload со схемами API, повторный seed без POST, неизвестный
  результат POST и мутации, привязка журнала к поколению базы, ограничения
  reset, пагинация 125 записей (пропуск/дубль/порядок/total), статистика,
  реальный HTTP-клиент с mock transport и исключение прогрева из замеров.

## Фактическое состояние среды

Одно административное соединение к локальному PostgreSQL использовано
**только для чтения**, с `default_transaction_read_only=on`, для проверки
наличия целевой базы: `mountain_fairytale_load` **отсутствует**.

Не выполнялись создание/сброс БД, миграции, массовое наполнение, запуск или
остановка API, реальные измерения. `.env` и `.env.qa` не переписывались.
Записей в существующие QA/production-базы не было; API 8001 не останавливался.
CORE/MANUAL не изменены. Flutter-код, бизнес-правила, финансовые алгоритмы
и миграции бизнес-сущностей не менялись. Релиз не выполнялся.

## Изменённые и новые файлы

- `scripts/load/manage.py` — init/check/start launcher/migrate/reset/status/report.
- `scripts/load/load.ps1` — Windows-обёртка, безопасная остановка только 8002.
- `scripts/load/plan.py` — воспроизводимые профили 1000/5000 и 5000/20000.
- `scripts/load/seed.py` — штатный HTTP seed и восстановление журнала.
- `scripts/load/verify.py` — независимые инварианты и страницы истории.
- `scripts/load/benchmark.py` — прогрев, HTTP timings/errors/throughput, CPU/RAM API.
- `src/common/infra/db/postgres/alembic/load_guard.py` — отдельная защита.
- `src/common/infra/db/postgres/alembic/migrations/env.py` — подключение load guard;
  существующий `qa_guard.py` не изменён.
- `tests/qa/test_load_tools.py` — 48 безопасных тестов.
- `docs/qa/stages/05-resilience-load.md` — полная инструкция.
- `docs/qa/README.md`, `docs/qa/progress.md`, `docs/qa/stages/README.md` — статус/ссылки.
- Этот короткий отчёт. Локальные журналы/секреты исключены существующим `.gitignore`.

## Следующее действие владельца

Проверить защитные механизмы и отдельно разрешить создание load-базы и
наполнение main. Затем выполнить init → migrate → start → check → seed →
verify → benchmark concurrency 1 и 2. High требует отдельного явного запуска
и разрешённого reset только load-данных после сохранения результатов main.

Реальная интеграция нагрузочного PostgreSQL/API и скорость наполнения ещё
не проверены. Baseline производительности отсутствует; SLA не установлен.
Автоматическая QA-029 подготовлена, но ещё не выполнена на массовой базе;
ручная прокрутка Flutter — **PENDING OWNER**. Аварии и конкурентная работа
остаются за пределами этого блока.
