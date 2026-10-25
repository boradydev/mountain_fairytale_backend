# GlitchTip: установка, обслуживание и восстановление

Этап 3А — работающий приёмник и дашборд. Код этапа 3Б (SDK FastAPI/Flutter
и выдача клиентской конфигурации) подготовлен и проверен реальными событиями.
Проверка диска/статусов бэкапов включена на VM. Активация SDK в рабочих
приложениях выполняется обычными выпуском backend и обновлением Flutter;
разработческая сборка не заменяет разрешённый production deploy.

## Состав и адреса

Отдельный Compose-проект `mountain-fairytale-monitoring` в
`/opt/mountain-fairytale-monitoring`: GlitchTip **6.2.6** (digest закреплён),
своя PostgreSQL 17 и готовый backup-сервис. Valkey не используется; фоновые задачи
выполняются all-in-one сервисом с очередью PostgreSQL. Рабочая БД API отделена.
Включены только ошибки: uptime, OTLP logs, MCP, cold storage и публичная
регистрация отключены. Docker stdout ротируется, 3 файла по 10 МБ на контейнер.

- Дашборд по VPN: `http://10.77.50.11:8080`.
- Дашборд по текущей LAN: `http://192.168.0.25:8080`.
- Организация `Mountain Fairytale`, проекты `backend`, `flutter`, `operations`.
- Firewall пропускает порт 8080 только из `LAN_INTERFACE` + `LAN_SUBNET`
  и с VPN-IP разработчика `/32`, как и API. Порты обеих PostgreSQL не публикуются.

HTTP принят для LAN/VPN. На роутере порт не пробрасывается. Доступ в дашборд
требует входа; публичный ключ DSN позволяет приём событий, но не администрирование.
`GLITCHTIP_PUBLIC_URL` определяет канонические ссылки/DSN в интерфейсе. Доступ
через второй адрес разрешён отдельно через allowed hosts и trusted origins.
Будущая интеграция Flutter будет формировать DSN для выбранного LAN/VPN-адреса.

## Установка

Сначала настроить [backend](first-install.md) и [VPN](support-vpn.md).
Все команды ниже — в Bash Ubuntu. Получить проверенную версию эксплуатационных
файлов из репозитория; обычный backend deploy их не доставляет.

В `/opt/mountain-fairytale` должны находиться актуальные:

- `scripts/deploy/network_firewall.py` и `lan_firewall.sh`;
- `init_monitoring_env.py`, `check_monitoring_firewall.py`, `setup_monitoring.py`,
  `export_monitoring_config.py` в `scripts/deploy/`;
- `ensure_monitoring_network.py` для общей внутренней сети Docker;
- для этапа 3Б — `configure_monitoring_events.py`, `operations_check.py` и
  unit/timer `mountain-fairytale-operations.*`;
- `deploy/monitoring/compose.yaml`, `deploy/mountain-fairytale-monitoring.service`.

Перед заменой файлов сохранить защищённую копию конфигурации, остановить
deploy timer и дождаться текущей операции по [обслуживанию](maintenance.md).
Далее, подставив свой LAN-IP и VPN-IP:

```sh
set -euo pipefail
cd /opt/mountain-fairytale
sudo python3 -m scripts.deploy.init_monitoring_env .env \
  --lan-host 192.168.0.25 --vpn-host 10.77.50.11
sudo install -d -m 0700 /opt/mountain-fairytale-monitoring
sudo install -m 0644 deploy/monitoring/compose.yaml /opt/mountain-fairytale-monitoring/compose.yaml
sudo install -m 0644 deploy/mountain-fairytale-monitoring.service /etc/systemd/system/
sudo docker compose --project-directory /opt/mountain-fairytale-monitoring \
  --env-file /opt/mountain-fairytale/.env config --quiet
sudo systemctl daemon-reload
sudo python3 -m scripts.deploy.ensure_monitoring_network
sudo systemctl reload mountain-fairytale-firewall.service
sudo docker compose --project-directory /opt/mountain-fairytale-monitoring \
  --env-file /opt/mountain-fairytale/.env pull
sudo systemctl enable --now mountain-fairytale-monitoring.service
sudo systemctl start mountain-fairytale-deploy.timer
```

Генератор дописывает отсутствующие ключи, не заменяет существующие секреты и
не читает локальный development `.env`. Все значения остаются в **общем**
серверном `/opt/mountain-fairytale/.env` (0600). Полный `compose config` и
`config --environment` в консоль не выводить: они содержат секреты.
Если ключи уже были, проверить их в собственном приватном редакторе;
`GLITCHTIP_ENABLED` должен быть `true` перед reload и запуском.

Unit перед запуском проверяет наличие Docker firewall для порта мониторинга.
`GLITCHTIP_ENABLED` управляет разрешением в firewall, а не systemd: для отключения
сначала выполнить `systemctl disable --now mountain-fairytale-monitoring.service`,
затем изменить `.env` и reload firewall. Одна правка флага не останавливает контейнеры.

Создать администратора (подставить свой email; пароль в команду не передаётся):

```sh
cd /opt/mountain-fairytale
sudo python3 -m scripts.deploy.setup_monitoring --email admin@example.com
sudo cat .deploy/monitoring-admin-initial.password
```

Последнюю команду выполнять только в своём терминале, не отправлять результат
в чат/логи. Скрипт создаёт организацию, команду и 3 проекта, при повторном запуске
не меняет существующий пароль. Войти в дашборд и сменить начальный пароль;
после сохранения нового пароля начальный файл можно удалить.
Метаданные проектов находятся в root-only `.deploy/monitoring-projects.json`.
Это снимок первоначальной настройки, не источник истины при дальнейших изменениях
через UI; актуальные ключи хранятся в БД и видны в настройках проектов.

## Переменные общего `.env`

| Переменная | Значение генератора / назначение |
| --- | --- |
| `GLITCHTIP_ENABLED` | `true`; включить защиту порта в firewall |
| `GLITCHTIP_PORT` | `8080`, отличается от порта API |
| `GLITCHTIP_PUBLIC_URL` | `http://VPN_IP:8080`, канонический адрес интерфейса |
| `GLITCHTIP_ALLOWED_HOSTS` | LAN/VPN IPv4, `127.0.0.1`, `localhost`, `web` |
| `GLITCHTIP_TRUSTED_ORIGINS` | HTTP origins LAN/VPN с портом |
| `GLITCHTIP_POSTGRES_PASSWORD` | Случайная hex-строка; для подключения через DATABASE_URL сохранять URL-безопасный формат |
| `GLITCHTIP_SECRET_KEY` | Случайный секрет GlitchTip, обязателен для восстановления |
| `GLITCHTIP_RETENTION_DAYS` | `30`, события/файлы/releases и автоматическая очистка |
| `GLITCHTIP_BACKUP_KEEP` | `3` успешные daily-копии |
| `GLITCHTIP_BACKUP_TIME` | `17:15`, Europe/Moscow; отдельно от рабочего backup в 17:00 |
| `GLITCHTIP_BACKUP_S3_PREFIX` | `mountain-fairytale/monitoring`; имя БД `glitchtip` добавляет backup-сервис |

Общие S3 endpoint/bucket/region и AWS-ключи используются из того же `.env`.
Они передаются только backup-контейнеру; GlitchTip и его PostgreSQL их не получают.
Каждый сервис получает явный список ENV, весь `.env` в контейнеры не подключается.
Изменение секрета/пароля БД существующего тома — отдельная согласованная операция,
не способ переинициализации через `.env`. Поведение рабочего backup не меняется.

При смене LAN-IP обновить allowed hosts/trusted origins; при необходимости также
public URL. Применить firewall и пересоздать `web`/`backup` с нужным окружением.
Если меняется порт, одновременно обновить origins/public URL, firewall и публикацию.
Compose-проект и имя БД не менять, рабочие тома не удалять.

## Проверки, логи и резервные копии

Удобная функция для текущего Bash-сеанса:

```sh
dc() { sudo docker compose --project-directory /opt/mountain-fairytale-monitoring \
  --env-file /opt/mountain-fairytale/.env "$@"; }
dc ps
sudo systemctl is-active mountain-fairytale-monitoring.service
sudo systemctl is-enabled mountain-fairytale-monitoring.service
curl --fail http://10.77.50.11:8080/_health/
dc logs --tail 80 web
dc logs --tail 50 backup
dc run --rm --no-deps backup status
```

Для ручной актуальной копии использовать ту же категорию `daily`:

```sh
dc run --rm --no-deps backup run --category daily
```

Так все штатные копии мониторинга используют единый лимит 3. Категории manual/
predeploy в этом процессе не используются: они имеют независимые лимиты и
создали бы дополнительные копии. Расписание и catch-up обслуживает постоянный
backup-контейнер; не cron хоста. После пропуска создаётся одна догоняющая копия.
Архив читается обратно из S3 и сверяется по SHA-256 до публикации manifest/ротации.

Отдельно экспортировать конфигурацию и используемые uploads после изменений:

```sh
cd /opt/mountain-fairytale
sudo python3 -m scripts.deploy.export_monitoring_config \
  ".deploy/monitoring-recovery-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
```

Комплект включает **весь общий server.env с секретами**, закреплённый Compose,
метаданные и `uploads.tar`. Это не дамп БД. Файл root-only 0600, имена не
перезаписываются. Скопировать комплект в защищённое хранилище разработчика вне
клиентского ПК, не коммитить и не публиковать. Пока он лежит только в VM,
от потери клиентского ПК он не защищает. При активной загрузке символов перед
экспортом согласовать паузу загрузок; новые файлы требуют обновления комплекта.
Еженедельный экспорт VM выполняет владелец и дополняет эту процедуру.

## Пробное восстановление БД

Применяется к изолированному временному контейнеру, не к рабочим томам.
Сначала `dc run --rm --no-deps backup status`, выбрать полный
`lastSuccess.manifestKey`. В том же Bash-сеансе:

```sh
MANIFEST_KEY='ПОЛНЫЙ_КЛЮЧ_JSON_MANIFEST'
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
RESTORE_FILE="monitoring-restore-$STAMP.dump"
CHECK_CONTAINER="mf-monitoring-restore-$STAMP"
dc run --rm --no-deps backup download --manifest "$MANIFEST_KEY" --output "/state/$RESTORE_FILE"
sudo docker run -d --name "$CHECK_CONTAINER" --network none \
  -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=restore_check \
  postgres:17-bookworm@sha256:858bb5e98eed02eb8cafbcdc007f9a65d1b613972028944a8ec2133ccaf80d27
until sudo docker exec "$CHECK_CONTAINER" pg_isready -h 127.0.0.1 -U postgres -d restore_check; do sleep 1; done
dc run --rm --no-deps -T --entrypoint cat backup "/state/$RESTORE_FILE" \
  | sudo docker exec -i "$CHECK_CONTAINER" pg_restore \
    -U postgres -d restore_check --exit-on-error --no-owner --no-acl
sudo docker exec "$CHECK_CONTAINER" psql -U postgres -d restore_check -X -v ON_ERROR_STOP=1 \
  -c 'SELECT count(*) FROM users_user' \
  -c 'SELECT name, slug FROM projects_project' \
  -c 'SELECT count(*) FROM projects_projectkey' \
  -c 'SELECT count(*) FROM issue_events_issueevent'
```

Запускать с `set -euo pipefail`. `trust` разрешён только этому контейнеру без
сети/портов. Сверить проекты, пользователей, ключи и контрольные события с копией.
После успешной проверки удалить только созданные тестовые ресурсы:

```sh
sudo docker rm -f -v "$CHECK_CONTAINER"
dc run --rm --no-deps --entrypoint rm backup "/state/$RESTORE_FILE"
```

## Восстановление самого GlitchTip после потери

1. Сохранить уцелевшие диски/тома для диагностики. Подготовить новую установку
   с **пустыми отдельными томами мониторинга**, прежнюю не затирать.
2. Вернуть проверенные эксплуатационные файлы и конфигурацию из recovery bundle.
   При восстановлении только мониторинга не заменять весь рабочий `.env` API:
   перенести нужные GLITCHTIP-поля и проверить S3-доступ в приватном редакторе.
   Сохранить прежний `SECRET_KEY` и версию Compose/образа, заменить сетевые адреса.
3. Не включать monitoring unit и не запускать `web`/`backup`: они могут создать
   новую схему/копию пустой БД. Запустить только `dc up -d --wait postgres`.
   Убедиться, что в целевой БД нет прикладных таблиц.
4. Скачать нужную пару manifest/dump через одноразовый `backup download`
   (`--no-deps`). Восстановить в **новую пустую** БД `glitchtip` через
   `dc exec -T postgres pg_restore -U glitchtip -d glitchtip --exit-on-error --no-owner --no-acl`,
   подав бинарный поток так же, как в пробном восстановлении.
5. Вернуть `uploads.tar` в новый том uploads, сохранив числовые UID/GID и права.
   Не распаковывать непроверенные архивы поверх работающего приложения.
6. Применить firewall, запустить `web` на прежней версии и проверить вход,
   проекты, DSN и тестовое событие. Затем включить unit/backup. Обновлять
   GlitchTip до новой версии только отдельным шагом после успешного восстановления.

Восстанавливается состояние на момент выбранных копий. Свежие события после
дампа не восстанавливаются; новые/удалённые файлы могут требовать подходящего
по времени recovery bundle. Восстановление всего приложения из экспорта VM —
отдельная операция владельца, возвращающая назад также рабочую БД API.

## Обновление и приёмка

Перед обновлением: актуальная проверенная daily-копия БД и recovery bundle,
прочитанные release notes, согласованное окно. Заменить закреплённые версию/digest
в Compose, выполнить `dc pull`, `dc up -d --wait`, проверить UI/события/backup.
Миграции GlitchTip выполняются при старте; произвольный откат образа после них
не гарантирован. Не выполнять глобальные `down -v`/`volume prune`.

25 октября 2026 проверено на VM:

- Владелец вошёл в дашборд; созданы три проекта и администратор.
- UI и тестовые события по LAN/VPN; два события сохранены в БД.
- Посторонний тестовый интерфейс заблокирован firewall.
- Daily-копия загружена/проверена в Timeweb S3; из неё в изолированной PostgreSQL
  восстановлены 1 пользователь, 1 организация, 3 проекта, 3 ключа, 2 события,
  170 миграций; отпечатки ключей совпали.
- На восстановленной копии событие возрастом 40 дней удалено штатной очисткой
  с retention 30; свежие события сохранены. Рабочие события не удалялись.
- Весь monitoring unit остановлен/запущен, API в это время оставался ready.
  Автозапуск включён; после добавления GlitchTip полная VM ещё не перезагружалась.
- В спокойном состоянии web использует около 165–175 МиБ, его PostgreSQL около
  40–75 МиБ; это замер без рабочей нагрузки, не лимит и не гарантия пиков.

Осталось владельцу сохранить recovery bundle вне клиентского ПК и принять
автозапуск GlitchTip при следующей согласованной перезагрузке Ubuntu.
Результаты этапа 3Б и порядок активации описаны ниже.

## Этап 3Б: SDK и эксплуатационные события

Python использует `sentry-sdk` 2.73.0 с FastAPI/Starlette; Flutter —
`sentry_flutter` 10.2.0. Сохраняются версия приложения, окружение, тип исключения
и стек (файл/функция/строка). Значения исключений заменяются общим текстом;
request body, headers, query, user, extras, breadcrumbs и локальные переменные
не отправляются. Это сознательно ограничивает подробности ради защиты данных.
Сессии, скриншоты, native crash capture, performance/profiling и поток INFO-логов
в эту интеграцию не входят. Flutter native crash capture выключен; проверены
именно Dart/Flutter исключения Windows. Уже перехваченные бизнес-кодом ошибки
требуют явного capture, если они должны считаться неожиданной диагностикой.

Ожидаемые бизнес-ошибки backend не считаются авариями. Flutter не отправляет
ApiException и обычные ошибки соединения/таймауты; HTTP 5xx диагностируется
backend. Неожиданные ошибки JSON-декодирования явно захватываются клиентом.
Также явно захватываются ошибки формирования PDF и отправки на печать в
существующих обработчиках; отмена пользователем не считается аварией.
`X-Request-ID` генерируется сервером для каждого HTTP-запроса и возвращается
также при 500. Его можно сопоставить с серверным логом/тегом GlitchTip;
Flutter сохраняет ID в ответе/ApiException и диагностике некорректного JSON.
Одинаковый тип/стек ограничивается одним событием в минуту, кеш дедупликации
ограничен 128 сигнатурами. Очередь SDK ограничена 30 событиями в памяти;
собственного долговременного хранилища/гарантированной досылки нет.

### Конфигурация и выпуск

Все ключи остаются в общем `/opt/mountain-fairytale/.env`:

| Переменная | Назначение |
| --- | --- |
| `SENTRY_DSN` | Backend DSN: внутреннее имя `glitchtip:8000`; пусто отключает SDK |
| `SENTRY_ENVIRONMENT` | `production` по умолчанию; тестовые события используют отдельные окружения |
| `FLUTTER_MONITORING_ENABLED` | `true` для выдачи активной конфигурации; по умолчанию `false` |
| `FLUTTER_SENTRY_PUBLIC_KEY` | Только публичный hex-ключ Flutter-проекта, 32 символа |
| `FLUTTER_SENTRY_PROJECT_ID` | Идентификатор Flutter-проекта |
| `GLITCHTIP_PORT` | Внешний порт для Flutter, по умолчанию 8080 |
| `OPERATIONS_SENTRY_DSN` | Для хостового проверяющего скрипта: `127.0.0.1:8080`, проект operations |

`configure_monitoring_events.py` заполняет отсутствующие/пустые SDK-поля из
root-only `.deploy/monitoring-projects.json`, не печатает ключи. Если проекты
или ключи менялись в UI, сначала актуализировать метаданные повторным
`setup_monitoring --email ...` либо ввести актуальные DSN/публичные поля вручную.
Существующие непустые SDK-поля сохраняются. Административный пароль не выдаётся
API и не используется для приёма событий.

API подключается к GlitchTip через общую внешнюю Docker-сеть
`mountain-fairytale-observability`, alias `glitchtip`. Сеть создаётся отдельным
idempotent скриптом до запуска обоих unit; её существование не требует
работающего GlitchTip. PostgreSQL и backup не включаются в общую сеть.
Остановка monitoring Compose не удаляет эту сеть и не мешает API.

На существующей VM перед выпуском передать актуальные Compose, unit и скрипты
с сохранением защищённой копии конфигурации и паузой deploy timer по
[обслуживанию](maintenance.md), затем:

```sh
cd /opt/mountain-fairytale
sudo python3 -m scripts.deploy.ensure_monitoring_network
sudo python3 -m scripts.deploy.configure_monitoring_events
sudo install -m 0644 deploy/monitoring/compose.yaml /opt/mountain-fairytale-monitoring/compose.yaml
sudo install -m 0644 deploy/mountain-fairytale.service /etc/systemd/system/
sudo install -m 0644 deploy/mountain-fairytale-monitoring.service /etc/systemd/system/
sudo install -m 0644 deploy/mountain-fairytale-operations.service /etc/systemd/system/
sudo install -m 0644 deploy/mountain-fairytale-operations.timer /etc/systemd/system/
sudo systemctl daemon-reload
dc up -d --no-deps --wait web
sudo systemctl enable --now mountain-fairytale-operations.timer
sudo systemctl start mountain-fairytale-operations.service
sudo systemctl start mountain-fairytale-deploy.timer
```

Этот подготовительный шаг на текущей VM уже выполнен, API не пересоздавался.
После пользовательских commit/PR/CI выбрать новый backend SHA штатным workflow,
дождаться deploy/ready и проверить `GET /public/monitoring/config`. Затем выпустить
Flutter обычным путём. Никаких ручных правок Python внутри рабочего API-контейнера.
Старая версия backend возвращает 404: новый Flutter продолжает работать и
повторяет загрузку конфигурации через минуту.

Endpoint публичный, чтобы мониторинг мог настроиться до входа пользователя.
Ответ — обычный `StdResponse`, в `data` только `enabled`, `publicKey`, `projectId`,
`port`, `environment`. При отключении/некорректных полях возвращается
`enabled=false`, ключ/проект — null. Host и backend DSN не выдаются.
Flutter формирует HTTP DSN для хоста выбранного API на порту мониторинга.
При смене сервера старый HTTP-клиент закрывается, устаревшие ответы конфигурации
отбрасываются; до получения новой конфигурации SDK не отправляет события.

### Проверка диска и бэкапов

`mountain-fairytale-operations.timer`: первый запуск через 3 минуты после boot,
дальше через 5 минут после окончания проверки. Только Ubuntu `/`: warning
при свободном месте меньше 20%, critical меньше 10%. Windows не проверяется.
У обоих постоянных backup-контейнеров читается `/state/status.json`:
`lastError` → backup_failed, `cleanupRequired` → cleanup_failed,
ошибка чтения отмечается только в journal и не превращается в uptime-алерт.
Давность/пропуск расписания не вызывает алерт. Для преддеплойной копии читается
булево `backupError` из `.deploy/state.json`: оно ставится при сбое этапа backup
и снимается после успешного преддеплойного backup. Ни текст ошибки, ни ENV
из deploy state не отправляются. Ручные CLI-копии проверяются по результату
команды; гарантии регистрации краткого ручного сбоя этим observer нет.

Проверка отправляет смену состояния и восстановление через совместимый
протокол GlitchTip в operations. Готовый backup-образ не меняется, S3-ключи
не копируются в GlitchTip. Повтор неизменного состояния подавляется в root-only
`.deploy/operations-status.json` (это состояние проверки, не очередь событий).
При сбое отправки текущее проблемное состояние проверяется заново в следующий
раз. Короткий сбой, исчезнувший между проверками, может не попасть в GlitchTip.
Recovery — отдельное info-событие в той же группе; issue автоматически не
помечается resolved через административный API.

```sh
sudo systemctl list-timers mountain-fairytale-operations.timer
sudo journalctl -u mountain-fairytale-operations.service -n 40 --no-pager
```

### Проверки 3Б от 25 октября

- Python SDK через изолированный FastAPI/TestClient отправил одну неожиданную
  ошибку со стеком/версией; ожидаемая бизнес-ошибка и дубль не отправлены.
- Flutter SDK через opt-in HTTP-приёмку отправил событие в реальный GlitchTip,
  после смены конфигурации на отключённую отправка прекратилась. Тестовый
  приватный маркер удалён, событие сохранено в БД со стеком.
- Проверены warning → critical → recovery и ошибки обоих backup на подставных
  состояниях, без заполнения диска или повреждения рабочей копии. Приняты
  тестовые события `acceptance-operations`, повтор того же состояния подавлен.
  Дополнительно проверены сбой/восстановление преддеплойной копии; отсутствие
  работающего контейнера не создаёт uptime-алерт.
- Внутренний маршрут Docker `glitchtip:8000` проверен. API/backup/PG продолжают
  работать на прежних контейнерах, operations timer включён.
- Рабочие приложения ещё требуют обычного выпуска; приёмочные события SDK
  не означают, что старый production-образ уже содержит новый код.

После окончательного ввода и проверки выпусков заново сформировать recovery
bundle и **один раз** положить его в приватный S3 в зашифрованном виде; ключ
восстановления сохранить отдельно. Это оставленная владельцем мини-задача,
сейчас она не выполнена. Старый `monitoring-recovery-final-20261025.tar.gz`
не объявляется актуальным комплектом после изменения инфраструктуры.
