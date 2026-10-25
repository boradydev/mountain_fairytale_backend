# Серверные ENV: где хранятся и как менять

Рабочий каталог Ubuntu — `/opt/mountain-fairytale`. Все команды выполняются там.
Серверный `.env` принадлежит владельцу установки, права 0600, каталог 0700.
Они не копируются из окружения разработки и не коммитятся. Не запускайте
`source .env` и не публикуйте вывод полного `docker compose config`.

## Файл `.env`

Создаётся `python3 scripts/deploy/init_env.py .env --image ОБРАЗ --bind-host IP ...`.
Скрипт генерирует секреты и отказывается перезаписывать существующий файл.
Перед первым запуском выбирается реальный опубликованный образ; значение
`mountain-fairytale-api:1.0.0` по умолчанию в генераторе/шаблоне осталось для
исторической локальной сборки и без такой сборки не существует.

| Переменная | Значение/обязательность | Назначение |
| --- | --- | --- |
| `API_IMAGE` | Обязательна; `ghcr.io/boradydev/mountain_fairytale_backend@sha256:...` | Точный runtime-образ. После первого запуска меняется pull-deployer-ом |
| `API_BIND_HOST` | Обязательна; генератор: `0.0.0.0` | Все IPv4-интерфейсы; до публикации применить firewall. Для ограниченной привязки можно указать LAN-IP |
| `API_PORT` | Генератор: `8000`; для firewall обязательна | Опубликованный порт API; такое же значение нужно firewall |
| `LAN_SUBNET` | Генератор: `192.168.0.0/24` | Разрешённая IPv4-сеть клиентов; передать свою |
| `LAN_INTERFACE` | Генератор: `eth0` | Интерфейс VM; проверить через `ip -br -4 address` |
| `POSTGRES_DB` | Обязательна; генератор: `mountain_fairytale` | Имя БД, также часть S3-префикса |
| `POSTGRES_USER` | Обязательна; генератор: `mountain_fairytale` | Роль PostgreSQL |
| `POSTGRES_PASSWORD` | Обязательна; случайная строка | Пароль роли, не передавать клиенту |
| `JWT_SECRET_KEY` | Обязательна; случайная строка | Подпись токенов; хранить в защищённой резервной копии |
| `ADMIN_USERNAME` | Обязательна; генератор: `admin` | Имя bootstrap-администратора новой БД |
| `ADMIN_PASSWORD` | Обязательна; случайная строка | Только первоначальное создание администратора |
| `GEOAPIFY_API_KEY` | Необязательна; пусто | Без неё недоступны карты, геокодирование и оптимизация |
| `GEOAPIFY_TILE_CACHE_MAX_BYTES` | `2147483648` | Лимит кэша карт (2 ГБ), отдельный Docker volume |
| `BACKUP_IMAGE` | По умолчанию 0.1.0 с digest из `compose.backup.yaml` | Независимый образ backup, обычный API deploy его не обновляет |
| `BACKUP_S3_ENDPOINT` | `https://s3.twcstorage.ru` | Endpoint хранилища |
| `BACKUP_S3_BUCKET` | Бакет текущей установки из Compose | При новой установке явно указать свой существующий бакет |
| `BACKUP_S3_REGION` | `ru-1` | Регион S3-подписи |
| `BACKUP_S3_PREFIX` | `mountain-fairytale/production` | Имя БД добавляется автоматически; независимым БД нужны разные префиксы |
| `BACKUP_TIME` | `17:00` | Плановое время |
| `BACKUP_TIMEZONE` | `Europe/Moscow` | Часовой пояс расписания, имена архивов остаются UTC |
| `BACKUP_KEEP` | `30` | Лимит daily-копий |
| `BACKUP_MANUAL_KEEP` | `30` | Независимый лимит manual |
| `BACKUP_PREDEPLOY_KEEP` | `30` | Независимый лимит predeploy |

Параметры `SUPPORT_VPN_*` для туннеля на хосте описаны в [VPN поддержки](support-vpn.md).
Они остаются в том же `.env`, но в контейнеры не передаются.
Параметры `GLITCHTIP_*` и их применение описаны в [мониторинге](monitoring.md).
Мониторинг использует тот же серверный `.env` через явный `--env-file`,
но отдельный Compose-проект и свою БД.

Это параметры Compose и настройки хоста. Константы
`POSTGRES_HOST=postgres`, `POSTGRES_PORT=5432`, `JWT_ALGORITHM=HS256`, время
access/refresh токенов 15 минут/90 дней и внутренний порт API 8000 задаёт Compose.
Добавление одноимённой строки в `.env` само по себе эти константы не изменит.

## S3-ключи в общем `.env`

Добавляются скрытым вводом: `python3 scripts/deploy/init_backup_env.py .env`.

| Переменная | Назначение |
| --- | --- |
| `AWS_ACCESS_KEY_ID` | Обязательный Access Key отдельного S3-пользователя |
| `AWS_SECRET_ACCESS_KEY` | Обязательный Secret Key |

Все настройки хранятся в одном серверном `.env`. Compose передаёт контейнерам
только перечисленные в их `environment` переменные. API/PostgreSQL ключей не получают.
Не подключайте весь `.env` через `env_file`. Генератор экранирует ключи для dotenv;
при ручном редактировании учитывайте синтаксис Docker Compose, особенно `$` и кавычки.
Нужны права list/get/put/delete в выделенном бакете/префиксе. Дополнительные
необязательные настройки самого сервиса (таймауты, интервалы повторов) описаны
в [его README](https://github.com/boradydev/postgres_s3_backup#настройки).
Если параметра нет в `environment` Compose, сначала добавьте туда явное сопоставление
с переменной `.env`. Произвольные переменные `.env` автоматически в контейнер не попадают.

## Переход с отдельного `backup.env`

API deploy не обновляет локальную инфраструктуру. В рабочий каталог VM нужно передать
новые `compose.backup.yaml`, `scripts/deploy/init_backup_env.py`, оба systemd unit
`mountain-fairytale-backup.service` и `mountain-fairytale-deploy.service`, а также
`scripts/deploy/install_pull_deploy.sh`.
Перед заменой остановите `mountain-fairytale-deploy.timer`, дождитесь завершения
активного деплоя и бэкапа, сохраните защищённую копию конфигурации.
Затем в `/opt/mountain-fairytale`:

```sh
python3 scripts/deploy/init_backup_env.py .env --from-legacy backup.env
sudo docker compose -f compose.yaml -f compose.backup.yaml config --quiet
sudo install -m 0644 deploy/mountain-fairytale-backup.service /etc/systemd/system/
sudo install -m 0644 deploy/mountain-fairytale-deploy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo docker compose -f compose.yaml -f compose.backup.yaml up -d --no-deps --force-recreate backup
sudo docker compose -f compose.yaml -f compose.backup.yaml run --rm --no-deps backup status
sudo systemctl start mountain-fairytale-deploy.timer
```

После успешной проверки удалите старый `backup.env` из рабочего каталога.
Перенос не выводит значения и не удаляет исходный файл. Если старый файл содержит
дополнительные настройки, скрипт остановится: сначала перенесите их явно в `.env`
и `environment` Compose. Повторный импорт не заменяет уже существующие ключи.

Переход существующей VM `192.168.0.25` выполнен 25 октября 2026 года:
S3-ключи в общем `.env` сверены с прежним окружением без вывода значений,
Compose и systemd-файлы обновлены, пересоздан только backup из прежнего образа.
Ручная копия загружена и проверена в Timeweb S3; scope и состояние расписания
сохранены. API/PostgreSQL не пересоздавались и не перезапускались, таймер доставки
возобновлён. Старый `backup.env` убран из рабочего каталога в защищённый архив
конфигурации под `.deploy/config-backups/` (каталоги 0700, файлы секретов 0600).

## Изменить настройки работающего приложения

Смена `API_BIND_HOST` требует также применения firewall и проверки доступа с Windows.
Полный порядок: [смена IP-адреса VM](maintenance.md#сменить-ip-адрес-vm).

Открыть `nano .env` в собственном SSH-терминале.
Сохранить права и проверить Compose, не раскрывая значения:

```sh
cd /opt/mountain-fairytale
chmod 0600 .env
sudo docker compose -f compose.yaml -f compose.backup.yaml config --quiet
```

Обычные настройки API, например Geoapify, применить пересозданием API:

```sh
sudo docker compose up -d --no-deps --force-recreate --wait api
```

S3-ключи, расписание и лимиты — пересозданием backup:

```sh
sudo docker compose -f compose.yaml -f compose.backup.yaml up -d --no-deps --force-recreate backup
sudo docker compose -f compose.yaml -f compose.backup.yaml run --rm --no-deps backup status
```

Обычный `docker restart` передаёт прежнее окружение контейнера.
Операции обслуживания выполняются вне текущей миграции/деплоя: при необходимости
отключите timer по [инструкции обслуживания](maintenance.md).

Особые случаи:

- `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB` не переинициализируют
  существующий том. Смена пароля требует согласованного изменения роли в БД
  и клиентов; произвольное редактирование этих полей ломает подключение.
- `ADMIN_PASSWORD` не меняет пароль существующей учётной записи. Используйте
  `sudo docker compose exec api python -m src.common.cli.main admin change-password`.
- Смена `JWT_SECRET_KEY` делает текущие токены недействительными — потребуется вход.
- Новый IP/порт/подсеть требуют проверки firewall и адреса в Flutter. При
  `API_BIND_HOST=0.0.0.0` смена только LAN-IP не требует пересоздания API.
  Цепочки MF_* обновляются при reload; старые правила прежней версии
  DOCKER-USER проверяются отдельно при миграции.
- Endpoint/бакет/префикс backup связаны с состоянием тома. Для другого места
  хранения сервису нужен отдельный том состояния; не удаляйте рабочий
  `backup_state`, чтобы обходить ошибку scope. Это отдельная миграция хранилища.

## Что хранить отдельно для восстановления

В защищённой копии вне Windows-ПК: `.env`, перечень нужных
Compose/systemd/скриптов и версия конфигурации, данные установленного API-образа
и его миграций (из `.deploy/state.json`/каталога выпуска), доступы к S3 и SSH.
Секреты не кладутся рядом с публичными manifest/release-файлами в GitHub.
Дамп одной БД не содержит пароли/роли всего PostgreSQL-кластера или ENV.

При переносе сохраните имена БД/бакет/префикс для чтения выбранного manifest,
но замените сетевые параметры на адрес новой VM. Подробности: [restore.md](restore.md).
