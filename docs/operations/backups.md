# PostgreSQL → Timeweb S3

Сервис находится в отдельном локальном проекте
`C:\Users\alexv\PycharmProjects\postgres_s3_backup`. У него собственные
Dockerfile, poetry.lock, тесты и CI. Backend использует готовый образ через
`compose.backup.yaml`; изменения API для бэкапов не требуются.

## Выбранное хранилище

- Endpoint: `https://s3.twcstorage.ru`.
- Бакет: `0865f0b6-5416-4bab-8573-2fca06751a80`, приватный, холодный.
- Регион: `ru-1`.
- Отдельный S3-пользователь: `mountain_fairytale_backend`, «Чтение и запись»
  только для этого бакета.
- Префикс: `mountain-fairytale/production/mountain_fairytale/`.

Реальные ключи не записываются в Git или GitHub Secrets. Файл `backup.env`
находится только на VM, читается Docker и передаётся только backup-контейнеру.
API и PostgreSQL S3-ключей не получают. Пример без значений:
`deploy/backup.env.example`.

## Подготовка и первый запуск

Используется публичный образ `ghcr.io/boradydev/postgres_s3_backup:0.1.0`.
В `compose.backup.yaml` дополнительно закреплён проверенный digest
`sha256:5ad9268297245e100bc1dcd8cd83339b84035d4834fd6b4cf2f1d0ce4e266c87`.
Авторизация GHCR на VM не нужна. Для обновления укажите новый проверенный
тег/digest через `BACKUP_IMAGE` в серверном `.env` или обновите значение в Compose.

На VM передать `compose.backup.yaml`, `scripts/deploy/init_backup_env.py`,
`deploy/mountain-fairytale-backup.service`, затем скачать образ:

```sh
cd /opt/mountain-fairytale
sudo docker pull ghcr.io/boradydev/postgres_s3_backup:0.1.0@sha256:5ad9268297245e100bc1dcd8cd83339b84035d4834fd6b4cf2f1d0ce4e266c87
```

В личном терминале владельца на Windows:

```powershell
ssh -t ma4etea@192.168.0.25 "cd /opt/mountain-fairytale && python3 scripts/deploy/init_backup_env.py backup.env"
```

По очереди ввести S3 Access Key и Secret Key. Ввод скрыт, в shell history
значения не попадают. Файл создаётся с правами 0600, существующий файл
скрипт не перезаписывает. Не присылать ключи в чат.

Далее на VM (после ввода ключей):

```sh
cd /opt/mountain-fairytale
sudo docker compose -f compose.yaml -f compose.backup.yaml config --quiet
sudo docker compose -f compose.yaml -f compose.backup.yaml run --rm backup run --category daily
sudo docker compose -f compose.yaml -f compose.backup.yaml run --rm backup status
```

После подтверждения реальной загрузки и восстановления включить расписание:

```sh
sudo install -m 0644 deploy/mountain-fairytale-backup.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mountain-fairytale-backup.service
```

Unit запускается после основного стека и останавливается перед ним.
При остановке ПК отсутствие копий не считается аварией.

## Расписание и ротация

- Ежедневно 17:00 Europe/Moscow, без внешнего cron/GitHub Actions.
- При пропуске — одна копия после следующего старта и готовности PostgreSQL.
- Состояние в отдельном томе `backup_state` переживает пересоздание контейнера.
- Повтор после сбоя использует незавершённый архив и тот же S3-ключ.
- Подтверждение: загрузка → полное скачивание и SHA-256 → публикация manifest
  → чтение manifest → запись успеха → ротация старых.
- Полное скачивание каждой новой копии расходует исходящий трафик S3.
  Это проверка реальных данных, а не только метаданных или ETag.
- Независимые лимиты: `BACKUP_KEEP=30` для `daily`, `BACKUP_MANUAL_KEEP=30`
  для `manual`, `BACKUP_PREDEPLOY_KEEP=30` для `predeploy`. Их можно переопределить
  в серверном `.env`; категории не вытесняют друг друга. Ручная команда `run`
  по умолчанию создаёт `manual` и не засчитывает выполнение расписания.
- Ошибка дампа/загрузки/проверки не запускает удаление старых копий.
- Ошибка очистки не отменяет успех новой копии; журнал удаления позволяет
  повторить незавершённую очистку при следующей проверке.
- Неподтверждённые архивы не считаются пригодными копиями без manifest.
- Ошибки пока пишутся в логи/status; доставка в GlitchTip — этап мониторинга.

Дополнительная копия перед миграцией:

```sh
sudo docker compose -f compose.yaml -f compose.backup.yaml run --rm backup run --category predeploy
```

Код возврата 0 означает подтверждённый бэкап; ненулевой код блокирует миграцию.
Операции сериализуются блокировкой общего тома, без параллельного pg_dump.
При неудаче сохранённого задания сервис не удаляет его и не объявляет успех:
нужно исправить доступ/связь/место и повторить, не удаляя том состояния.

## Проверка восстановления

В `status.lastSuccess.manifestKey` указан ключ JSON-manifest последней копии.

```sh
sudo docker compose -f compose.yaml -f compose.backup.yaml run --rm backup download --manifest <manifestKey> --output /state/restore.dump
```

Скачанный архив проверяется по SHA-256. Существующий restore.dump не
перезаписывается; для следующей проверки использовать новое имя.
Для полного восстановления нужно создать **отдельный временный контейнер**
PostgreSQL 17 без опубликованных портов, скопировать в него скачанный архив,
выполнить pg_restore с `--exit-on-error --no-owner --no-acl`, затем проверить
таблицы, alembic_version и чтение записей. Не запускать restore поверх
рабочей БД. Проверка с реальным Timeweb выполнена 22 октября 2026; результат приведён ниже.

Дамп содержит одну БД. Роль/пароль, расширения и серверная конфигурация
восстанавливаются отдельно из инструкции и защищённого серверного окружения.
Секреты и конфигурацию нужно резервировать отдельно. Сам dump не шифруется
на стороне клиента: используется приватный бакет и HTTPS.

## Состояние этапа

На 22 октября 2026: образ 0.1.0 опубликован в публичном GHCR; 29 unit-тестов проверяют
расписание, догоняющий запуск, ротацию, ошибки и безопасное скачивание.
Полный цикл с настоящим pg_dump/pg_restore проверен на отдельной тестовой
PostgreSQL и S3-эмуляторе, восстановленная запись прочитана обратно.
Реальная загрузка в Timeweb и восстановление из него выполнены 22 октября 2026:

- `backup.env` принадлежит `ma4etea`, права `0600`; значения не выводились.
- Ежедневный архив 38 613 байт загружен в согласованный префикс бакета,
  прочитан обратно, проверены размер/SHA-256 и JSON-manifest.
- Архив повторно скачан из Timeweb и восстановлен с `pg_restore --exit-on-error`
  в отдельный PostgreSQL 17 с `--network none`, без подключения к рабочему тому.
- Версия Alembic `c8a2d91e470f` и числа строк всех 15 таблиц `public`
  совпали с исходной базой; в восстановленной `cars` одна запись, `employees`
  одна запись, `events` шесть записей. Значения пользовательских полей не выводились.
- Временный PostgreSQL и скачанный для проверки файл удалены.
- `mountain-fairytale-backup.service` установлен, `enabled` и `active`;
  контейнер `backup` работает, API/PostgreSQL остаются healthy.
- Часовой пояс VM — Europe/Moscow; расписание 17:00, лимиты 30/30/30.
  Первый запуск планировщика использовал сохранённый coveredSlot без второго дампа.

Преддеплойная категория включена в реализованный pull-деплой API: после
остановки API и до миграций/совместимого отката создаётся подтверждённая копия;
при её неудаче дальнейшая установка блокируется. Порядок — в
[backend-deploy.md](backend-deploy.md). Доставка ошибок в GlitchTip остаётся этапом 3.
Простой Windows/VM допустим, внешний uptime-контроль не включён.
