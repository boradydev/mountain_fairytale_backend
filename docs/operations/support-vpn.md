# Удалённая поддержка через SSTP

SSTP-клиент работает на Ubuntu VM как systemd-служба, вне Docker. VM сама
подключается к Keenetic разработчика. Проброс портов у клиента не требуется.
WireGuard остаётся резервным вариантом; автоматического переключения нет.
GlitchTip устанавливается отдельно позднее.

## Адреса и доступ

- Сегмент Keenetic: `my_support_host`, `10.77.50.1/24`, без Wi-Fi/портов LAN.
- Отдельная учётная запись VM: постоянный SSTP IP `10.77.50.11`.
- Отдельная учётная запись разработчика: постоянный SSTP IP `10.77.50.10`.
- DHCP для SSTP не нужен; адреса назначает SSTP-сервер. NAT выключен.
- Между VPN-клиентами должна быть разрешена связь на Keenetic. Домашняя сеть
  разработчика и клиентская LAN не объединяются; не разрешайте доступ сегмента
  к другим сегментам роутера. Ограничения Keenetic задаются владельцем отдельно.

Публикация API — `API_BIND_HOST=0.0.0.0`, порт 8000. В `DOCKER-USER` разрешены
только `LAN_INTERFACE` + `LAN_SUBNET` и `support0` + IP разработчика `/32`.
Остальные новые соединения к опубликованному порту API блокируются.
На самой VM через `support0` разработчику разрешены SSH/22 и ping; прочий
входящий трафик и пересылка из VPN блокируются. PostgreSQL наружу не публикуется.
Доступ к будущему GlitchTip потребуется разрешить отдельно после его установки.

Адрес клиента Flutter у пользователей — `http://LAN_IP_VM:8000`,
у разработчика — `http://10.77.50.11:8000`. Вход в приложение обычной учётной
записью admin. SSH используется напрямую к VM, без туннелей отдельных портов.

## Переменные общего `.env`

Все настройки находятся в `/opt/mountain-fairytale/.env`, права `0600`.
Они не передаются API/backup-контейнерам. Не выполняйте `source .env`.

| Переменная | По умолчанию / смысл |
| --- | --- |
| `SUPPORT_VPN_ENABLED` | `false`; при `true` firewall разрешает IP разработчика. Запуск службы управляется systemd отдельно |
| `SUPPORT_VPN_PROTOCOL` | `sstp`; установщик поддерживает только SSTP |
| `SUPPORT_VPN_HOST` | Обязательный DNS-адрес Keenetic без `https://`, пути и порта |
| `SUPPORT_VPN_PORT` | `443`; с Keenetic проверен стандартный порт 443 |
| `SUPPORT_VPN_USERNAME` | Обязательный логин отдельной учётной записи VM |
| `SUPPORT_VPN_PASSWORD` | Обязательный пароль этой учётной записи |
| `SUPPORT_VPN_SUBNET` | `10.77.50.0/24` в генераторе `.env`; обязательна для установщика |
| `SUPPORT_VPN_EXPECTED_IP` | `10.77.50.11` в генераторе; постоянный адрес VM на Keenetic |
| `SUPPORT_VPN_ADMIN_IP` | `10.77.50.10` в генераторе; постоянный адрес рабочего ПК |
| `SUPPORT_VPN_INTERFACE` | `support0`; имя интерфейса VM, оставьте постоянным |

При ручном вводе пароля учитывайте синтаксис Compose dotenv: одинарные кавычки
позволяют сохранить `$` буквально. Пароль сюда, в Git и в команды не вставляется.
Адреса VPN должны отличаться от LAN и сетей Docker/других VPN.

## Установка на новой VM

Сначала выполните [первую установку](first-install.md). Нужны актуальные
`scripts/deploy/network_firewall.py`, `lan_firewall.sh`, `install_support_vpn.py`
и оба unit из `deploy/`. При обновлении существующей установки сохраните
защищённую копию `.env` и прежних файлов, остановите deploy timer и дождитесь
окончания активного деплоя по [инструкции обслуживания](maintenance.md).
Держите доступ через LAN/консоль Hyper-V до окончания проверки VPN.

Команды выполняются на Ubuntu из `/opt/mountain-fairytale`:

```sh
sudo apt-get update
sudo apt-get install -y --no-install-recommends sstp-client ppp ca-certificates
nano .env
chmod 0600 .env
sudo python3 -m scripts.deploy.install_support_vpn --check
sudo python3 -m scripts.deploy.install_support_vpn
sudo install -m 0644 deploy/mountain-fairytale-firewall.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl reload mountain-fairytale-firewall.service
sudo systemctl enable --now mountain-fairytale-support-vpn.service
```

В `.env` заполните таблицу и установите `SUPPORT_VPN_ENABLED=true` перед reload.
`--check` проверяет конфигурацию и TLS без записи файлов. Установщик проверяет
цепочку и имя TLS-сертификата, сохраняет PPP-профиль с паролем только для root
(`/etc/ppp/peers/mountain-fairytale-support`, `0600`) и ip-up hook (`0700`).
Сам установщик не запускает туннель. Ошибка TLS не обходится `--cert-warn`.
Для Keenetic не требуется обязательное PPP MPPE: шифрование обеспечивает TLS,
а PPP-аутентификация — MSCHAPv2. Системные DNS и основной шлюз не заменяются.
Через VPN добавляется только маршрут `10.77.50.0/24`.

После подключения проверьте SSH по VPN и API по LAN. Если API ещё привязан
только к LAN-IP, **после успешного применения firewall** поменяйте в `.env`
`API_BIND_HOST=0.0.0.0` и пересоздайте только API из прежнего образа:

```sh
sudo docker compose config --quiet
sudo docker compose -f compose.yaml -f compose.backup.yaml up -d --no-deps --force-recreate --wait api
```

Проверьте API с обоих ПК, затем возобновите deploy timer. При миграции со старого
firewall прежнее IP-правило удаляется только после успешной проверки, как описано
в [обслуживании](maintenance.md#сменить-ip-адрес-vm). Не очищайте DOCKER-USER целиком.

## Проверки и изменение настроек

```sh
systemctl is-active mountain-fairytale-support-vpn.service
systemctl is-enabled mountain-fairytale-support-vpn.service
ip -4 address show support0
ip -4 route
sudo journalctl -u mountain-fairytale-support-vpn.service -n 40 --no-pager
sudo iptables -nvL MF_API
sudo iptables -nvL MF_VPN_INPUT
```

`active` означает работающий процесс, а не готовый туннель: проверьте адрес и
маршрут. С Windows разработчика: `ssh ma4etea@10.77.50.11`, а в браузере
`http://10.77.50.11:8000/health/ready`. Readiness должна вернуть `data.status=ready`.
Пароль SSH/sudo и пароль SSTP — разные учётные данные.

При изменении VPN `.env` недостаточно обычного restart: повторите установщик,
reload firewall и `sudo systemctl restart mountain-fairytale-support-vpn.service`.
При изменении логина/пароля используйте LAN-доступ, иначе потеряете текущий VPN-сеанс.
Изменения unit требуют `systemctl daemon-reload`. `restart` firewall может
остановить зависимые службы приложения; используйте **reload** для смены правил.

Служба запускается при включении VM и повторяет попытку через 10 секунд после
завершения процесса. Выключенный Keenetic/интернет не мешает API работать по LAN.
Для отключения VPN: `sudo systemctl disable --now mountain-fairytale-support-vpn.service`,
затем `SUPPORT_VPN_ENABLED=false` и reload firewall. Одного `false` недостаточно
для остановки уже работающего туннеля. API и pull-деплой не зависят от VPN.

## Приёмка 25 октября 2026

На VM проверены: TLS, MSCHAPv2, IP `10.77.50.11`, маршрут поддержки без смены
основного шлюза; SSH и HTTP readiness с Windows через VPN; HTTP через LAN;
запуск API при остановленном VPN; блокировка API из постороннего тестового
интерфейса со счётчиком DROP; автоматическое восстановление после завершения
процесса (`NRestarts=1`, снова доступны SSH и API). Пересоздан только API из прежнего образа,
PostgreSQL и backup сохранили контейнеры. Deploy timer возобновлён.
После перезагрузки Ubuntu владельцем 25 октября проверен автоматический запуск
Docker, firewall, API/PostgreSQL, backup, deploy timer и SSTP. SSH-подключение
выполнено через `10.77.50.11`, readiness с Windows получена через VPN и LAN,
правила MF_* восстановлены, основной шлюз остался прежним. Ошибок systemd нет;
PostgreSQL штатно завершился перед ребутом и запустился без ошибок восстановления.
Это проверка перезагрузки Ubuntu; запуск всего Windows-ПК и аварийное отключение
питания в неё не входили. Вход Flutter через VPN проверяется владельцем отдельно.
