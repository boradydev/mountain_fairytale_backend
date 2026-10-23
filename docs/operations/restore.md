# Восстановление PostgreSQL из S3

Есть два разных сценария: регулярная проверка копии в **изолированном контейнере**
и возврат данных на **новую пустую VM**. Эти команды не являются процедурой
перезаписи работающей БД. Все блоки выполняются в Bash на Ubuntu.

## Что нужно иметь

- Доступ к бакету, исходные endpoint/регион/префикс и имя БД.
- Полный ключ JSON-manifest нужной копии. Последний виден в
  `backup status → lastSuccess.manifestKey`; для старой копии выберите manifest
  через S3-консоль в категории daily/manual/predeploy, проверьте дату UTC.
- Custom-дамп и соответствующий manifest должны оставаться парой. `download`
  проверяет размер/SHA-256 архива; одиночный dump без manifest не считается
  подтверждённой копией сервиса.
- Сведения о версии/образе backend, схеме и конфигурации на момент копии.
  Они хранятся отдельно: manifest backup не содержит commit SHA API.
- Свободное место для скачанного дампа, временной БД и её WAL. Для восстановления
  большого дампа это больше размера сжатого архива.

По умолчанию имена `.env`/Compose/БД берутся из текущего проекта. Значения
подключений не надо вставлять в командную строку или shell history.
Нужные роли/расширения не равнозначны backup всего PostgreSQL-кластера:
текущая установка создаёт роль через POSTGRES_USER, `pg_restore --no-owner
--no-acl` назначает объекты роли восстановления; расширения должны поддерживаться
целевым PostgreSQL. Используем закреплённый PostgreSQL 17 из Compose.

## Пробное восстановление в отдельный контейнер

Не останавливает API и не подключает рабочий `postgres_data` к тестовому
контейнеру. Результат — отдельная временная БД `restore_check`, без публикации
портов и без сети. Проверку рекомендуется повторять периодически.

### 1. Скачать и проверить архив

Введите **реальный полный ключ** manifest вместо примера. Для новой попытки
используется новое имя: существующий файл download не перезаписывает.

```sh
set -euo pipefail
cd /opt/mountain-fairytale
MANIFEST_KEY='ВСТАВЬТЕ_ПОЛНЫЙ_КЛЮЧ_JSON_MANIFEST'
RESTORE_FILE="restore-check-$(date -u +%Y%m%dT%H%M%SZ).dump"
sudo docker compose -f compose.yaml -f compose.backup.yaml run --rm --no-deps backup \
  download --manifest "$MANIFEST_KEY" --output "/state/$RESTORE_FILE"
```

При ошибке не переходите к restore. Ключ должен принадлежать текущим
бакету/префиксу/имени БД сервиса. Файл находится в томе backup_state, не в
папке проекта на VM. Эта операция только читает S3, ротацию не запускает.

### 2. Создать независимый PostgreSQL

```sh
PG_IMAGE=$(sudo docker compose config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["postgres"]["image"])')
CHECK_CONTAINER="mf-restore-check-$(date -u +%Y%m%dT%H%M%SZ)"
sudo docker run -d --name "$CHECK_CONTAINER" --network none \
  -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=restore_check "$PG_IMAGE"
for attempt in $(seq 1 60); do
  if sudo docker exec "$CHECK_CONTAINER" pg_isready -h 127.0.0.1 -U postgres -d restore_check >/dev/null 2>&1; then break; fi
  sleep 2
done
sudo docker exec "$CHECK_CONTAINER" pg_isready -h 127.0.0.1 -U postgres -d restore_check
```

Полный Compose config здесь передаётся прямо в Python для извлечения публичного
имени образа; он не выводится в терминал/файл. Не включайте `set -x`.
`trust` разрешён только для этого изолированного временного контейнера без сети;
к рабочему Compose он не применяется. Docker создаёт для PG отдельный анонимный
том; рабочие тома в `docker run` не монтируются. Проверка TCP loopback ждёт
окончательного запуска сервера, а не временного Unix-сервера инициализации.

### 3. Восстановить и проверить

```sh
sudo docker compose -f compose.yaml -f compose.backup.yaml run --rm --no-deps -T \
  --entrypoint cat backup "/state/$RESTORE_FILE" \
  | sudo docker exec -i "$CHECK_CONTAINER" pg_restore \
      -U postgres -d restore_check --exit-on-error --no-owner --no-acl
sudo docker exec "$CHECK_CONTAINER" psql -U postgres -d restore_check -X -v ON_ERROR_STOP=1 \
  -c 'SELECT version_num FROM alembic_version' \
  -c '\dt public.*' \
  -c 'SELECT count(*) AS employees_count FROM employees'
```

`-T` отключает TTY у источника бинарного потока; `pipefail` не скрывает ошибку
первой команды. Проверить ревизию, ожидаемые таблицы и контрольные количества
записей на момент выбранной копии. Успешный download ещё не означает успешный
restore, а SQL-проверки не заменяют приёмку значимых бизнес-данных.

### 4. Удалить только тестовые ресурсы

После проверки сохранить дату копии, ревизию и результат без пользовательских
полей/секретов. Затем из того же SSH-сеанса:

```sh
sudo docker stop "$CHECK_CONTAINER"
sudo docker rm -v "$CHECK_CONTAINER"
sudo docker compose -f compose.yaml -f compose.backup.yaml run --rm --no-deps -T \
  --entrypoint rm backup "/state/$RESTORE_FILE"
```

Удаляется конкретный новый контейнер с его анонимным томом и скачанный тестовый
файл; S3-копия и `postgres_data` не затрагиваются. При ошибке проверки сохраните
контейнер для разбора и не удаляйте рабочие данные. Если SSH-сеанс потерян,
сначала найдите созданный `mf-restore-check-*` через `docker ps -a`, а не удаляйте
контейнеры/тома по глобальной маске.

## Восстановление на новой VM

Применяется после потери/переноса сервера. Старая рабочая VM, если ещё доступна,
остаётся сохранённой; переключение клиентов выполняется только после проверки.
Одновременные записи пользователей в старую и новую БД недопустимы.

### 1. Подготовить новую VM без API/миграций/планировщиков

Пройти разделы 1–3 [первой установки](first-install.md): Ubuntu, Docker,
эксплуатационные файлы, проверенный API-образ. На **новой** VM не должно быть
томов/контейнеров проекта от предыдущих попыток; если они есть, сначала
выяснить их происхождение, не запускать эти команды поверх данных.

Изолированная проба выше покажет `alembic_version`. Для первого скачивания
дампа и пробы в `.env` достаточно API_IMAGE из сохранённой конфигурации либо
одного из проверенных выпусков каталога: API при этом **не запускается**.
До запуска API выберите выпуск, совместимый с фактически восстановленной
ревизией/миграциями, и исправьте API_IMAGE. Для последующего upgrade нужен
отдельный проверенный план; эта процедура стартует с образа восстановленной схемы.

Вернуть `.env` из защищённого хранилища (права 0600), поправить
сетевые параметры и `API_IMAGE`. При отсутствии файлов создать их генераторами
из [справочника ENV](server-env.md), указав **исходное имя БД и S3-параметры**
для чтения manifest. Старый пароль роли не нужен для восстановления с
`--no-owner --no-acl` в новый PostgreSQL; новая роль создастся из нового ENV.

Сохранённый JWT secret позволяет не менять ключ подписи без необходимости;
при его утрате/замене пользователи войдут заново. Пароли сотрудников берутся
из дампа; ADMIN_PASSWORD не перезаписывает восстановленные учётные записи.
Токены/изменения, появившиеся после копии, в неё не входят.

Не переносить старый `.deploy/state.json` как подтверждение установки на новой
VM. Он полезен как справка о версиях, но история применения формируется заново.
Не включать deploy timer, API, backup-службу и не выполнять `alembic upgrade`
до окончания восстановления. Сначала только проверка конфигурации и скачивание:

```sh
set -euo pipefail
cd /opt/mountain-fairytale
chmod 0600 .env
sudo docker compose -f compose.yaml -f compose.backup.yaml config --quiet
sudo docker compose -f compose.yaml -f compose.backup.yaml pull backup
```

Копию можно скачать командой download из раздела выше с уникальным RESTORE_FILE.
Для изолированной пробы работающий основной PostgreSQL не нужен (`--no-deps`).
Не запускать `backup run/serve` с пустой базой: это может запустить ротацию
старых копий в общем S3-префиксе.

### 2. Создать новую БД и заполнить её дампом

Этот блок допустим **только если целевой том PostgreSQL новый и пустой**.
API и миграции ещё не запускались; база создана entrypoint-ом PostgreSQL:

```sh
sudo docker compose up -d --wait --wait-timeout 120 postgres
sudo docker compose exec -T postgres sh -c \
  'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -X -v ON_ERROR_STOP=1' <<'SQL'
SELECT count(*) AS public_tables FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
SQL
```

Ожидается `public_tables=0`. Если есть таблицы, остановитесь: не применяйте
`--clean`, `dropdb` или сброс схемы для продолжения этой инструкции.
После подтверждённого download и успешной изолированной пробы:

```sh
sudo docker compose -f compose.yaml -f compose.backup.yaml run --rm --no-deps -T \
  --entrypoint cat backup "/state/$RESTORE_FILE" \
  | sudo docker compose exec -T postgres sh -c \
      'exec pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --exit-on-error --no-owner --no-acl'
sudo docker compose exec -T postgres sh -c \
  'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -X -v ON_ERROR_STOP=1 -c "SELECT version_num FROM alembic_version" -c "SELECT count(*) FROM employees"'
```

Если pg_restore завершился ошибкой, база может быть частично заполнена.
Не запускайте API и не повторяйте поверх неё restore вслепую; сохраните ошибку
и разберите причину. Новую попытку выполняют в отдельно подготовленной пустой БД.

### 3. Вернуть сервис в работу

1. Сверить восстановленную ревизию с каталогом/миграциями выбранного API-образа.
   Прочитать контрольные данные в приватном терминале, не ограничиваться health.
2. Установить firewall и основную systemd-службу командами раздела 5
   [первой установки](first-install.md), **пропустив** строку запуска migrate.
   Запустить API; readiness и версия/commit должны соответствовать выбранному образу.
3. Проверить вход, данные и бизнес-сценарии на одном клиенте. При другом адресе
   VM указать новый URL в настройках Flutter и войти заново. Старый клиент без
   настройки URL сначала обновить до версии с этой возможностью.
4. Только после проверки сделать новую S3-копию восстановленной БД, затем
   включить backup-службу. Исходную пригодную копию сохраните отдельно;
   проверьте, что единственный пишущий сервер использует правильный префикс.
5. Через GitHub разрешить этот образ как `deploy` с новым deploymentId,
   затем подключить timer по разделу 7 первой установки. Если глобальное указание
   содержит более новую версию, она не должна примениться без проверки её миграций.
6. Прежнюю VM выводить из эксплуатации только после подтверждения владельца.
   Потерю данных после момента выбранного backup автоматический restore не устраняет.

Изолированная проба не перезаписывает рабочую БД. Перенос на новую VM требует
проверки отсутствия данных в целевой БД и осознанного переключения клиентов.
Автоматический rollback приложения и восстановление из копии — разные операции.
