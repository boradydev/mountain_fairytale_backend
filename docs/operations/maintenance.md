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
| На сервере новый IP, клиент ходит на старый | Изменить API_BASE_URL в Flutter Actions Variables и выпустить клиент; настройка уже установленного exe не меняется |

Не использовать для «починки» рабочей БД `down -v`, `volume prune`, тестовый
bootstrap, удаление `postgres_data`, автоматический downgrade или restore поверх
production. Не делать глобальную очистку Docker без разбора нужных образов/томов:
старые образы могут требоваться для отката. Восстановление — [отдельная процедура](restore.md).
