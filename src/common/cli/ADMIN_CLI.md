# CLI администратора

Из корня backend-проекта:

```sh
python -m src.common.cli.main admin info
python -m src.common.cli.main admin change-password
```

Первая команда показывает текущий логин и активность администратора.
Вторая показывает его логин и запрашивает новый пароль дважды со скрытым вводом.

Полная инструкция для Docker и локальной разработки:
[восстановление доступа администратора](../../../docs/operations/admin-access.md).
