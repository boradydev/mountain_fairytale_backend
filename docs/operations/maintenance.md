# Ежедневное обслуживание и типовые неполадки

Команды выполняются в Ubuntu из `/opt/mountain-fairytale`. Пароли/токены и полный
Compose config не публикуются. Состояние процесса systemd и готовность API —
разные вещи: oneshot unit может быть `active (exited)` при проблеме контейнера.

## Проверить состояние

```sh
cd /opt/mountain-fairytale
sudo docker compose -f compose.yaml -f compose.backup.yaml ps
curl --fail http://192.168.0.25:8000/health/ready
sudo python3 -m scripts.deploy.pull_deploy --status
sudo docker compose -f compose.yaml -f compose.backup.yaml run --rm --no-deps backup status
sudo systemctl list-timers mountain-fairytale-deploy.timer
df -h / /var/lib/docker
sudo docker system df
```

Используйте свой IP. Readiness: `data.status=ready` и ожидаемые версия/commitSha.
В deploy status: `phase`, `lastAttemptedId`, `current` и при сбое `lastError`.
В backup status: `coveredSlot`, `lastSuccess.manifestKey`, незавершённые операции
и ошибки. Статус backup не заменяет [пробное восстановление](restore.md).
Свободное место на Windows-томе с VHDX проверяется отдельно на Windows.

## Где смотреть логи

```sh
sudo docker compose logs --tail 100 api
sudo docker compose logs --tail 100 postgres
sudo docker compose -f compose.yaml -f compose.backup.yaml logs --tail 100 backup
sudo journalctl -u mountain-fairytale-deploy.service -n 80 --no-pager
sudo journalctl -u mountain-fairytale-firewall.service -n 40 --no-pager
```

Docker-логи ротируются, 3 файла по 10 МБ на сервис. GlitchTip пока не подключён.
На машине владельца можно просматривать приватные логи; перед передачей отчёта
уберите чувствительные данные. Обычное выключение ПК не является аварией.

## Остановить и запустить приложение

В согласованное время, когда пользователи закончили работу:

```sh
cd /opt/mountain-fairytale
sudo systemctl stop mountain-fairytale-deploy.timer
sudo systemctl show mountain-fairytale-deploy.service --property=ActiveState --property=SubState
```

Если deploy-service ещё выполняется, сначала дождитесь его завершения.
Остановка timer не прерывает уже начавшуюся миграцию. После этого:

```sh
sudo systemctl stop mountain-fairytale-backup.service
sudo systemctl stop mountain-fairytale.service
```

Тома остаются на месте. Для обычного запуска после обслуживания:

```sh
sudo systemctl start mountain-fairytale.service
sudo systemctl start mountain-fairytale-backup.service
curl --fail http://192.168.0.25:8000/health/ready
sudo systemctl start mountain-fairytale-deploy.timer
```

При наличии `.deploy/maintenance` не удаляйте его ради старта: сначала проверьте
прерванный deploy по [инструкции](backend-deploy.md#ошибки-и-прерванные-операции).
`stop` не меняет автозапуск после перезагрузки. Для длительного обслуживания
отключение enabled-служб планируется отдельно; контрольный reboot не выполняют
во время миграции.

## Сменить IP-адрес VM

Смена адреса не требует нового образа API, миграций или изменений PostgreSQL/S3.
Нужно обновить серверный `.env`, применить firewall и пересоздать только API
из того же образа. Обычный `docker restart` сохраняет старую привязку порта.

### 1. Подготовить обслуживание

Выберите время без работающих пользователей. Сохраните старые значения
`API_BIND_HOST`, `API_PORT`, `LAN_INTERFACE`, `LAN_SUBNET`: они понадобятся
для удаления прежнего правила firewall. Не выводите весь `.env` в консоль.
Откройте консоль VM в Hyper-V: при смене IP текущий SSH-сеанс может оборваться.

```sh
cd /opt/mountain-fairytale
sudo systemctl stop mountain-fairytale-deploy.timer
sudo systemctl show mountain-fairytale-deploy.service --property=ActiveState --property=SubState
```

Если deploy ещё выполняется (`activating`), дождитесь его окончания. Не меняйте
сеть во время миграции или активного бэкапа. При незавершённом deploy/maintenance
сначала выполните [восстановление доставки](backend-deploy.md#ошибки-и-прерванные-операции).
Не меняйте выбранный SHA и не запускайте новый deploy ради смены IP.

### 2. Изменить сеть и `.env`

Назначьте VM новый IPv4-адрес средствами Ubuntu/роутера и проверьте его:

```sh
ip -br -4 address
ip -4 route show default
cd /opt/mountain-fairytale
nano .env
```

В `.env` измените `API_BIND_HOST` на новый адрес VM. Если изменилась сеть клиентов
или имя сетевого интерфейса, обновите также `LAN_SUBNET` и `LAN_INTERFACE`.
`API_PORT` оставьте прежним, если менять порт не требуется. Не меняйте `API_IMAGE`,
параметры БД, секреты или S3-префикс. Не выполняйте `source .env`.

### 3. Применить firewall и пересоздать API

```sh
cd /opt/mountain-fairytale
chmod 0600 .env
sudo docker compose config --quiet
sudo systemctl restart mountain-fairytale-firewall.service
sudo systemctl is-active mountain-fairytale-firewall.service
sudo docker compose up -d --no-deps --force-recreate --wait api
sudo docker compose ps api
```

Firewall unit заново читает `/opt/mountain-fairytale/.env` и добавляет правило
для нового адреса. Ожидаемый статус unit — `active`; при ошибке сначала проверьте
его journal, не продолжайте запуск с неприменённым ограничением доступа.
Пересоздание вызывает короткий простой API; PostgreSQL и backup-контейнер остаются
на месте. Пересборка/публикация образа и `systemctl daemon-reload` не нужны.

### 4. Проверить доступ и убрать старое правило

Например, если новый адрес — `192.168.0.26`, порт — `8000`:

```sh
curl --fail --max-time 10 http://192.168.0.26:8000/health/ready
```

Подставьте свой адрес. Ожидаются `data.status=ready`, прежние версия и commitSha.
Откройте тот же URL с Windows-ПК пользователя; проверка только из самой VM
не подтверждает сетевой доступ и правила `DOCKER-USER`.

Скрипт добавляет новое правило, но не удаляет старое автоматически. После успешной
проверки удалите **только прежнее правило приложения**. В следующем примере
все четыре значения должны быть **старыми**, сохранёнными до редактирования `.env`:

```sh
OLD_IP=192.168.0.25
OLD_PORT=8000
OLD_INTERFACE=eth0
OLD_SUBNET=192.168.0.0/24
sudo iptables -w -S DOCKER-USER
if sudo iptables -w -C DOCKER-USER -i "$OLD_INTERFACE" -p tcp \
  -m conntrack --ctorigdst "$OLD_IP" --ctorigdstport "$OLD_PORT" \
  ! -s "$OLD_SUBNET" -j DROP 2>/dev/null; then
  sudo iptables -w -D DOCKER-USER -i "$OLD_INTERFACE" -p tcp \
    -m conntrack --ctorigdst "$OLD_IP" --ctorigdstport "$OLD_PORT" \
    ! -s "$OLD_SUBNET" -j DROP
fi
```

Эта команда рассчитана на смену IP: старый и новый адреса должны различаться.
Не удаляйте правило для нового адреса, не очищайте всю цепочку `DOCKER-USER`.
Если для приложения дополнительно настраивали UFW/роутер/Windows firewall,
обновите адрес и там. Наша инструкция не меняет эти внешние правила.

После проверки верните доставку:

```sh
sudo systemctl start mountain-fairytale-deploy.timer
sudo systemctl list-timers mountain-fairytale-deploy.timer
```

При ошибке оставьте таймер остановленным и проверьте IP, `.env`, journal firewall
и логи API. Для возврата восстановите прежний адрес VM и значения `.env`, затем
повторите применение firewall, пересоздание API и проверку. Данные БД не откатывайте.

### 5. Обновить адрес в клиенте

Во Flutter откройте ⋮ «Приложение» → «Настройки подключения…», укажите новый URL,
проверьте соединение, сохраните и подтвердите смену сервера. Войдите заново.
Настройка доступна также на экране входа и при недоступности сервера.
Повторите на каждом клиентском ПК; новая сборка не нужна.
`API_BASE_URL` в GitHub Actions задаёт только начальный адрес новых установок.
Старые клиенты без этой настройки нужно один раз обновить до версии с ней.
Подробности: [настройки Flutter](https://github.com/boradydev/mountain_fairytale/blob/master/docs/server-settings.md).

## Частые ситуации

| Симптом | Что проверить/сделать |
| --- | --- |
| `docker` не найден или Compose не понимает `format: raw` | Установить Engine/Compose plugin по `first-install.md`, проверить версии; не использовать старый `docker-compose` v1 |
| GHCR `denied`/`manifest unknown` | Видимость пакета Public, полный проверенный digest и запись каталога; не подменять образ на latest |
| Bootstrap JSON 404 | Полный SHA успешного master CI и наличие `deployment/releases/<SHA>.json` в GitHub; дождаться публикации каталога |
| `Cannot resolve deployment branch` / нет GitHub | Проверить DNS, HTTPS и `git ls-remote`; действующий API продолжает работать, timer повторит чтение |
| `API container not found` при pull-deploy | На новой VM сначала инициализировать БД/API по `first-install.md`; затем разрешить **новый** deploymentId через Select workflow |
| Workflow зелёный, API старый | Проверить timer/service/status на VM; зелёный Select означает только запись указания. Проверить доступ к GitHub/GHCR/S3 |
| Новый ID не устанавливается | Смотреть `lastError`, maintenance и миграции; не стирать `.deploy/state.json`, чтобы обойти проверки |
| `/health/live` 200, `/health/ready` 503 | Проверить PostgreSQL, место на диске и согласованность ENV. Не запускать init_env поверх существующей БД |
| API доступен в VM, недоступен с Windows | IP VM/Hyper-V-коммутатор, API_BIND_HOST, порт и LAN_INTERFACE/LAN_SUBNET, firewall unit/DOCKER-USER и сеть клиента |
| Не работают карты/геокодирование | `GEOAPIFY_API_KEY` в серверном `.env`, после изменения пересоздать API |
| Backup не проходит | S3-ключи/права на prefix, endpoint/регион, место и логи/status. Не удалять state/pending и старые S3-копии |
| Backup сообщает scope mismatch | Изменены endpoint/бакет/префикс/БД; нужен согласованный перенос/новый том состояния, не сброс старого |
| Смена ADMIN_PASSWORD ничего не изменила | Использовать `admin change-password`; ENV участвует только в первоначальном создании |
| На сервере новый IP, клиент ходит на старый | ⋮ «Приложение» → «Настройки подключения…» → новый адрес → проверка → сохранить → войти заново; после входа сначала нажать «Сменить сервер и выйти…» |

Не использовать для «починки» рабочей БД `down -v`, `volume prune`, тестовый
bootstrap, удаление `postgres_data`, автоматический downgrade или restore поверх
production. Не делать глобальную очистку Docker без разбора нужных образов/томов:
старые образы могут требоваться для отката. Восстановление — [отдельная процедура](restore.md).
