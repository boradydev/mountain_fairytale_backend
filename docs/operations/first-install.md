# Backend с нуля: Ubuntu VM → GHCR → API → S3 → обновления

Актуализировано 23 октября 2026 года. Это последовательная инструкция для
**новой Ubuntu VM с пустой БД**, без участия разработчика. Сборки уже публикуются
в публичный GHCR из репозитория `boradydev/mountain_fairytale_backend`.
Перенос TAR и сборка backend на сервере не нужны.

Если требуется вернуть **существующие данные на новый сервер**, сначала
прочитайте [восстановление](restore.md#восстановление-на-новой-vm): API, миграции
и расписание backup до восстановления запускать нельзя. Дамп не заменяет
резервную копию `.env` и сведений об установленном образе.

Все shell-команды ниже выполняются **в Bash внутри Ubuntu**, после входа по SSH.
Выполняйте блоки по очереди и не переходите дальше при ошибке. В каждом новом
сеансе сначала включите `set -euo pipefail` (Bash завершится при ошибке).
Переменные между блоками сохраняются в одном SSH-сеансе;
после переподключения задайте их снова.
Работающую VM по этой инструкции повторно не инициализируют.

## 1. Что подготовить

- Windows с Hyper-V и виртуализацией; VM поколения 2 с Ubuntu Server **24.04 LTS
  amd64**, без графического интерфейса. Скрипт установки рассчитан именно на 24.04.
  Для Secure Boot Ubuntu используется шаблон Microsoft UEFI Certificate Authority.
- Начальный ориентир VM: 2 vCPU, 4 ГБ RAM, 60 ГБ SSD; места должно хватать также
  под Docker-образы, БД и временные дампы. Это оценка для трёх пользователей.
- Внешний виртуальный коммутатор Hyper-V, собственный IPv4 VM, DHCP-резервация
  или статический адрес. Настроить автозапуск и корректное завершение VM в Hyper-V.
- Установленный OpenSSH Server и обычный пользователь Ubuntu с `sudo`.
  Постоянное passwordless sudo и группа `docker` не требуются.
- Исходящий HTTPS к GitHub, raw.githubusercontent.com, GHCR, репозиторию Docker
  и S3. Входящие соединения из GitHub и проброс порта роутера не требуются.
- Успешный **Backend CI** коммита `master`, опубликованный публичный API-образ
  и запись `releases/<SHA>.json` в ветке `deployment`. Их уже создаёт текущий CI.
- Приватный S3-бакет и ключи с list/get/put/delete в нужном бакете/префиксе.
  Для независимой второй установки выбирается **другой префикс**, чтобы её
  ротация не удаляла копии первой БД.

Пример существующей установки: `ma4etea@192.168.0.25`, сеть `192.168.0.0/24`,
API `http://192.168.0.25:8000`. Эти значения замените на свои.
Глобальное имя Compose-проекта — `mountain-fairytale`; каталог службы фиксирован:
`/opt/mountain-fairytale`.

## 2. Получить конфигурацию и установить Docker

На чистой VM установить инструменты и получить репозиторий в домашний каталог:

```sh
set -euo pipefail
sudo apt-get update
sudo apt-get install -y git python3 curl ca-certificates iptables nano
git clone https://github.com/boradydev/mountain_fairytale_backend.git "$HOME/mountain-fairytale-setup"
cd "$HOME/mountain-fairytale-setup"
git rev-parse HEAD
```

Используйте проверенную версию файлов из `master`; для воспроизводимости можно
перед копированием выполнить `git checkout --detach ПОЛНЫЙ_SHA_КОНФИГУРАЦИИ`.
Это версия **локальных Compose/systemd/скриптов**, она не обязана совпадать с
версией выбранного API-образа, но должна поддерживать его конфигурацию.
Просмотрите `scripts/deploy/install_docker.sh`, затем:

```sh
sudo sh scripts/deploy/install_docker.sh
sudo docker version
sudo docker compose version
python3 --version
ip -br -4 address
ip -4 route show default
```

Docker устанавливается из официального репозитория, служба включается,
часовой пояс — Europe/Moscow. Нужны Python 3.12+ на VM и актуальный Compose v2.
Python приложения, Poetry, PostgreSQL-клиент и Flutter
на VM устанавливать не требуется: они поставляются в образах.

Создать рабочий каталог и скопировать **только эксплуатационные файлы**:

```sh
sudo install -d -m 0700 -o "$USER" -g "$(id -gn)" /opt/mountain-fairytale
cd /opt/mountain-fairytale
test ! -e .env
install -m 0644 "$HOME/mountain-fairytale-setup/compose.yaml" .
install -m 0644 "$HOME/mountain-fairytale-setup/compose.backup.yaml" .
cp -R "$HOME/mountain-fairytale-setup/deploy" .
mkdir -p scripts
cp -R "$HOME/mountain-fairytale-setup/scripts/deploy" scripts/
sudo docker volume ls --filter label=com.docker.compose.project=mountain-fairytale
```

На чистой VM список томов этого проекта пуст. Если обнаружены `.env`, контейнеры
или тома прежней установки — остановитесь и используйте обслуживание/восстановление,
не удаляйте их ради повторения инструкции. Локальный `.env` разработки, БД,
виртуальное окружение и `.git` в рабочий каталог не копируются.

## 3. Выбрать готовый API-образ

В GitHub откройте успешный **Backend CI** ветки `master`, перейдите к коммиту
и скопируйте **полный 40-символьный SHA**. Это не тег `v1.0.0` и не номер workflow.
В примере следующего блока замените значение `RELEASE_SHA`:

```sh
cd /opt/mountain-fairytale
RELEASE_SHA='ВСТАВЬТЕ_ПОЛНЫЙ_SHA_УСПЕШНОГО_BACKEND_CI'
CATALOG_COMMIT=$(git ls-remote --exit-code https://github.com/boradydev/mountain_fairytale_backend.git refs/heads/deployment | cut -f1)
test -n "$CATALOG_COMMIT"
curl --fail --show-error --location \
  "https://raw.githubusercontent.com/boradydev/mountain_fairytale_backend/$CATALOG_COMMIT/releases/$RELEASE_SHA.json" \
  --output bootstrap-release.json
API_IMAGE=$(python3 - "$RELEASE_SHA" <<'PY'
import json
import sys
from pathlib import Path
from scripts.deploy.release_manifest import validate_release
release = validate_release(json.loads(Path('bootstrap-release.json').read_text()))
if release['commitSha'] != sys.argv[1]:
    raise SystemExit('Каталог содержит другой commit SHA')
print(release['image'])
PY
)
test -n "$API_IMAGE"
sudo docker pull "$API_IMAGE"
sudo python3 - <<'PY'
import json
from pathlib import Path
from scripts.deploy.pull_deploy import Runtime
from scripts.deploy.release_manifest import validate_release
project = Path('/opt/mountain-fairytale')
release = validate_release(json.loads((project / 'bootstrap-release.json').read_text()))
Runtime(project).inspect_release(release)
print('Digest, метки версии/SHA и миграции образа проверены')
PY
```

Это читает публичные метаданные и проверяет образ, не запускает API/миграции.
При 404 проверьте SHA и публикацию каталога; при denied проверьте видимость
пакета GHCR (**Public**). На сервере не нужен `docker login`.
Нельзя заменять проверенный digest на изменяемый `latest`.

## 4. Создать ENV и настроить сеть/S3

По выводу `ip` выберите свой адрес, подсеть и имя интерфейса (оно может отличаться
от `eth0`). Создать **новые** секреты для пустой БД:

```sh
cd /opt/mountain-fairytale
python3 scripts/deploy/init_env.py .env \
  --image "$API_IMAGE" \
  --bind-host 192.168.0.25 \
  --lan-subnet 192.168.0.0/24 \
  --lan-interface eth0
python3 scripts/deploy/init_backup_env.py .env
nano .env
```

Первый скрипт создаёт `.env` со случайными паролями/JWT, второй запрашивает S3-ключи
скрытым вводом в тот же `.env`. Генератор `.env` не заменяет существующий файл;
ввод S3 сохраняет остальные параметры и отказывается заменять существующие ключи.
В `.env` при необходимости
добавьте `GEOAPIFY_API_KEY`, параметры своего бакета и префикса. Пример S3-настроек:

```dotenv
BACKUP_S3_ENDPOINT=https://s3.twcstorage.ru
BACKUP_S3_REGION=ru-1
BACKUP_S3_BUCKET=ИМЯ_ВАШЕГО_БАКЕТА
BACKUP_S3_PREFIX=mountain-fairytale/new-install
BACKUP_TIME=17:00
BACKUP_TIMEZONE=Europe/Moscow
BACKUP_KEEP=30
BACKUP_MANUAL_KEEP=30
BACKUP_PREDEPLOY_KEEP=30
```

Для текущей установки бакет уже указан в Compose по умолчанию; явное значение
помогает при переносе на другой аккаунт/сервер. Ключи хранятся в том же `.env`,
но передаются **только backup-контейнеру**. Полный справочник: [server-env.md](server-env.md).
`new-install` — пример нового независимого префикса: выберите своё уникальное
имя. Не направляйте пустую новую БД в префикс работающей/восстанавливаемой БД;
для переноса данных используется отдельная процедура restore.

```sh
chmod 0600 .env
sudo docker compose -f compose.yaml -f compose.backup.yaml config --quiet
```

Не выполняйте `source .env` и не выводите полный `docker compose config`:
конфигурация содержит секреты. Редактируйте файлы в своём приватном терминале.
Доступ к API ограничивается доверенной локальной сетью; локальный HTTP принят
осознанно. API нельзя публиковать через роутер в интернет.

## 5. Инициализировать пустую БД и запустить API

**Только для новой пустой БД**, не для восстановления старых данных:

```sh
cd /opt/mountain-fairytale
sudo docker compose up -d --wait --wait-timeout 120 postgres
sudo docker compose --profile tools run --rm --no-deps migrate
sudo install -m 0644 deploy/mountain-fairytale-firewall.service /etc/systemd/system/
sudo install -m 0644 deploy/mountain-fairytale.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mountain-fairytale-firewall.service
sudo systemctl enable --now mountain-fairytale.service
sudo docker compose ps
curl --fail http://192.168.0.25:8000/health/live
curl --fail http://192.168.0.25:8000/health/ready
```

Первый `migrate` создаёт схему, API создаёт первоначального администратора.
Ожидается `data.status=ready`, версия и полный `commitSha` выбранного образа.
`/health/live` проверяет процесс, `/health/ready` — ещё и связь с БД (503 при сбое).
Порт PostgreSQL на хост не публикуется. Firewall unit ограничивает API через
DOCKER-USER; обычный UFW сам по себе не заменяет это правило. SSH не затрагивается.
При изменении адреса/подсети старые правила автоматически не удаляются.

Задать известный только владельцу пароль администратора:

```sh
sudo docker compose exec api python -m src.common.cli.main admin change-password
```

Ввод скрытый, пароль не передаётся в командной строке. Менять `ADMIN_PASSWORD`
в `.env` после создания пользователя для этого недостаточно.

## 6. Проверить и включить бэкапы

```sh
cd /opt/mountain-fairytale
sudo docker compose -f compose.yaml -f compose.backup.yaml pull backup
sudo docker compose -f compose.yaml -f compose.backup.yaml run --rm --no-deps backup run --category daily
sudo docker compose -f compose.yaml -f compose.backup.yaml run --rm --no-deps backup status
```

Команда должна завершиться кодом 0; `status.lastSuccess.manifestKey` указывает
подтверждённую копию в S3. Проверка включает скачивание и SHA-256, не только ETag.
Сначала выполните [пробное восстановление](restore.md#пробное-восстановление-в-отдельный-контейнер),
затем включите расписание:

```sh
sudo install -m 0644 deploy/mountain-fairytale-backup.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mountain-fairytale-backup.service
sudo docker compose -f compose.yaml -f compose.backup.yaml ps
```

Backup — постоянно запущенный отдельный контейнер. Ежедневно 17:00 МСК,
после пропуска — одна догоняющая копия. Успешная ручная команда категории daily
покрывает текущий срок расписания; ручные категории manual/predeploy его не заменяют.
Отсутствие копии из-за выключенного ПК не является аварией.

## 7. Подключить доставку новых версий из GitHub

Локальный pull-deployer **не создаёт начальную БД и API-контейнер с нуля**.
Его подключают только после шагов 5–6, когда API готов и S3 проверен.

В GitHub → Actions → **Select production backend** → Run workflow на `master`:
укажите выбранный полный SHA, `operation=deploy`. Файл указания общий для всех
VM, подключённых к этому репозиторию: учитывайте уже работающие установки.
Для новой VM используйте deploy, не rollback — истории образов на ней пока нет.

```sh
cd /opt/mountain-fairytale
sudo sh scripts/deploy/install_pull_deploy.sh
sudo systemctl start mountain-fairytale-deploy.service
sudo python3 -m scripts.deploy.pull_deploy --status
sudo systemctl list-timers mountain-fairytale-deploy.timer
sudo journalctl -u mountain-fairytale-deploy.service -n 60 --no-pager
```

Установщик включает timer, ручной start выполняет первую проверку сразу.
Ожидается `phase=succeeded` и `current.commitSha` нужного выпуска. Начальная
регистрация образа может выполнить ещё один преддеплойный backup и миграцию
без изменений — это штатно. Повтор успешно обработанного ID деплой не повторяет.

Дальше выпуск API разрешается по кнопке; Ubuntu скачивает образ, останавливает
API, делает S3-backup, применяет миграции и проверяет новый API. Зелёный workflow
выбора означает **запись указания**, фактический успех проверяется на VM.
Подробности отката и interrupted-состояния: [backend-deploy.md](backend-deploy.md).
Compose, systemd, ENV и backup-образ этим механизмом не обновляются.

## 8. Приёмка с клиентских ПК и после перезагрузки

1. С Windows открыть `http://192.168.0.25:8000/health/ready`; проверить вход
   и основные действия в Flutter, создать/прочитать тестовую запись.
2. Во Flutter через ⋮ «Приложение» → «Настройки подключения…» укажите URL VM, например
   `http://192.168.0.25:8000`, без дописывания `/app/v1`. Проверьте соединение,
   сохраните и войдите. GitHub Variable `API_BASE_URL` задаёт только начальный
   адрес; сохранённая настройка имеет приоритет. Старый клиент без настройки URL
   сначала обновите до версии с настройками. Новая сборка при смене IP не нужна.
3. Пересоздать только API и проверить сохранность записи:
   `sudo docker compose up -d --force-recreate --wait api`.
4. Проверить включённые службы и состояние контейнеров:

   ```sh
   sudo systemctl is-enabled docker mountain-fairytale-firewall mountain-fairytale mountain-fairytale-backup mountain-fairytale-deploy.timer
   sudo docker compose -f compose.yaml -f compose.backup.yaml ps
   ```

5. В согласованное время перезагрузить Ubuntu: `sudo reboot`, подключиться
   снова и проверить health, вход, запись и backup status. Затем отдельно
   проверить выключение/включение Windows и автозапуск Hyper-V.
6. До появления рабочих данных подтвердить S3/изолированный restore. После
   начала работы проверить новую копию уже рабочей базы.

## Где смотреть дальше

- [Параметры ENV и их изменение](server-env.md).
- [Бэкапы, расписание и S3](backups.md).
- [Проверка восстановления и перенос на новую VM](restore.md).
- [Выпуск/откат backend и журнал ошибок](backend-deploy.md).
- [Обслуживание и типовые неполадки](maintenance.md).

GlitchTip пока не подключён; диагностика — Docker/systemd и health endpoints.
Docker перезапускает завершившийся контейнер по `unless-stopped`, но не только
из-за unhealthy. Внешнего uptime-мониторинга и отдельного watchdog нет.
Не применяйте к рабочему стеку `down -v`, `volume prune`, тестовый bootstrap
или сброс схемы. Исторический [отчёт этапа 1](stage1-validation.md) описывает
прошлые проверки и не является текущей инструкцией установки.
