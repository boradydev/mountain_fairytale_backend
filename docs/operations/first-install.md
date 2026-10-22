# Первый запуск backend в Ubuntu VM

Этап 1 плана внедрения. Рабочая среда: Ubuntu Server 24.04 LTS, Hyper-V,
2 vCPU, 4 ГБ RAM, диск 60 ГБ на SSD. Один worker FastAPI.
VM может штатно выключаться вместе с Windows-ПК.

## 1. Docker и каталог приложения

Проверить содержимое `scripts/deploy/install_docker.sh`, затем на свежей Ubuntu:

```sh
sudo sh scripts/deploy/install_docker.sh
sudo install -d -m 0700 -o "$USER" -g "$(id -gn)" /opt/mountain-fairytale
```

Скрипт устанавливает Docker Engine и Compose plugin из официального
репозитория Docker, включает службу и задаёт Europe/Moscow. Существующий
Docker или нестандартная установка требуют отдельной проверки перед запуском.
Для выполнения команд далее используется `sudo docker`; добавление пользователя
в группу docker необязательно.

В `/opt/mountain-fairytale` поместить только конфигурацию из этой версии проекта:
`compose.yaml`, каталог `deploy/`, `scripts/deploy/` и готовый образ.
Локальный `.env`, виртуальное окружение, Git-история и содержимое БД не копируются.
Серверу не требуется собирать исходники.

## 2. Проверенная сборка

На машине разработки, из корня проекта:

```sh
docker build --target runtime --build-arg VCS_REF=<commit-sha> -t mountain-fairytale-api:1.0.0 .
docker image save -o api-image.tar mountain-fairytale-api:1.0.0
scp api-image.tar ma4etea@192.168.0.25:/opt/mountain-fairytale/
```

На VM:

```sh
cd /opt/mountain-fairytale
sudo docker image load -i api-image.tar
```

Это первоначальный ручной запуск. Ручной workflow и загрузка из GHCR относятся
к этапу 4. Непроверенный новый образ не подменяет уже опубликованную версию.
Для следующих изменений используйте другой тег/commit SHA согласно контракту.

## 3. Новая база и отдельные секреты

```sh
cd /opt/mountain-fairytale
python3 scripts/deploy/init_env.py .env --bind-host 192.168.0.25 --lan-subnet 192.168.0.0/24
```

Скрипт создаёт `.env` с правами 0600 и случайными паролями/JWT secret.
Существующий файл не перезаписывается. Учётные данные не печатаются.
Шаблон параметров — `deploy/.env.example`.

- `API_BIND_HOST`: закреплённый IPv4-адрес VM, а не `0.0.0.0`.
- `API_PORT`: 8000 по умолчанию.
- `LAN_SUBNET`, `LAN_INTERFACE`: разрешённая подсеть и интерфейс VM.
- `GEOAPIFY_API_KEY`: добавить серверный ключ для геокодирования/оптимизации
  и карт. Без ключа эти функции недоступны, остальные API могут работать.
- Кэш карт ограничен 2 ГБ по умолчанию и хранится в отдельном постоянном томе;
  это значение можно поменять через `GEOAPIFY_TILE_CACHE_MAX_BYTES`.

Не запускайте `docker compose config` без `--quiet` в записываемом терминале:
подставленная конфигурация содержит секреты.
Пароль первоначального `admin` смотрите только в собственном приватном терминале
на VM или замените значение до первого запуска. После создания администратора
смена `ADMIN_PASSWORD` в `.env` не меняет пароль существующей записи.

## 4. Миграции, сеть и запуск

```sh
cd /opt/mountain-fairytale
sudo docker compose config --quiet
sudo docker compose up -d --wait postgres
sudo docker compose --profile tools run --rm migrate
sudo install -m 0644 deploy/mountain-fairytale-firewall.service /etc/systemd/system/
sudo install -m 0644 deploy/mountain-fairytale.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mountain-fairytale-firewall.service
sudo systemctl enable --now mountain-fairytale.service
sudo docker compose ps
```

База создаётся с UTF-8/C.UTF-8 для поиска по кириллице. Порт PostgreSQL не
публикуется. `migrate` — отдельная разовая операция; запуск API/перезагрузка
VM не применяют миграции. Перед последующими миграциями рабочей БД обязателен
бэкап (реализуется на этапе 2).

Firewall unit ограничивает входящие Docker-соединения к опубликованному API
подсетью `LAN_SUBNET` через DOCKER-USER. SSH не затрагивается. Обычного UFW
недостаточно для ограничения опубликованных Docker-портов.
При изменении IP/порта/подсети сначала согласуйте и обновите правила:
скрипт добавляет правило идемпотентно, старые правила сам не удаляет.

API использует HTTP, поэтому доступ разрешается только доверенной локальной
сети. Не пробрасывать этот порт из интернета. На клиентских ПК endpoint:
`http://192.168.0.25:8000`. Существующий root path `/app/v1` также сохраняется;
при настройке Flutter проверить запрос к `/public/auth/users` и вход.

```sh
curl --fail http://192.168.0.25:8000/health/live
curl --fail http://192.168.0.25:8000/health/ready
```

`GET /health/live` проверяет работу процесса без обращения к БД.
`GET /health/ready` выполняет SELECT 1 через инфраструктурный слой с таймаутом
3 секунды: 200 при успехе, 503 при недоступной БД. Оба маршрута публичны,
используют StdResponse и возвращают `data.status`, `version`, `commitSha`.
Пароли, URL подключения, traceback и текст ошибки БД не возвращаются.
OpenAPI содержит версию из pyproject.toml.

Контейнер имеет healthcheck, но Compose не перезапускает процесс только из-за
unhealthy. `restart: unless-stopped` применяется при завершении контейнера.
Внешний uptime-мониторинг не настраивается.

## 5. Проверки перед рабочими данными

1. Войти администратором с Windows-ПК, создать тестовую запись через API
   и прочитать её обратно. Секреты и токены не сохранять в отчёте.
2. Пересоздать только API: `sudo docker compose up -d --force-recreate --wait api`.
   Проверить, что запись осталась.
3. Проверить `sudo systemctl is-enabled docker mountain-fairytale`.
4. По согласованию выключить/включить VM, затем Windows-ПК и проверить
   цепочку Hyper-V → Ubuntu → Docker → API/PostgreSQL и сохранность записи.
   Настройка Hyper-V выполняется на Windows-хосте отдельно от Ubuntu.
5. Проверить, что PostgreSQL не имеет опубликованного порта, API доступен
   только через выбранный адрес и правила сети активны.

Приёмка из интерфейса Flutter и реальное выключение Windows требуют
проверки владельцем; наличие unit-файла не означает, что весь автозапуск проверен.

## Обслуживание

```sh
cd /opt/mountain-fairytale
sudo docker compose ps
sudo docker compose logs --tail 100 api
sudo systemctl status mountain-fairytale --no-pager
```

Логи контейнеров ротируются: 3 файла по 10 МБ на сервис.
Остановка: `sudo systemctl stop mountain-fairytale`.
Запуск: `sudo systemctl start mountain-fairytale`.
Не применять `down -v`, `volume prune`, тестовый bootstrap или сброс схемы
к рабочему стеку. Интеграционные тесты выполняются на отдельной PostgreSQL.
Этап 1 ещё не включает S3-бэкапы, GlitchTip и автоматизированный ручной деплой.
