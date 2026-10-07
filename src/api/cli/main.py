import argparse
import asyncio
import getpass

import dotenv

from src.feat.employees.app.usecases.change_password import (
    ChangeEmployeePasswordDTO,
    ChangeEmployeePasswordUseCase,
)
from src.domain.common.const import SYSTEM_ACTOR_ID
from src.infra.bootstrap.admins.settings import AdminSettings
from src.infra.db.postgres.database import Postgres
from src.feat.employees.infra.employee_uow import EmployeesUOW
from src.infra.services.event_publisher.service import EventPublisher
from src.infra.services.password.service import PasswordService


async def change_admin_password() -> None:
    settings = AdminSettings()

    postgres = Postgres()
    event_publisher = EventPublisher(
        session_factory=postgres.session_factory,
    )
    password_service = PasswordService()

    uow = EmployeesUOW(
        session_factory=postgres.session_factory,
        event_publisher=event_publisher,
    )

    try:
        async with uow as _uow:
            admin = await _uow.employees.get_by_username(
                settings.ADMIN_USERNAME,
            )

            if admin is None:
                raise RuntimeError(
                    f"Администратор '{settings.ADMIN_USERNAME}' не найден.",
                )

            if admin.role != "admin":
                raise RuntimeError(
                    f"Пользователь '{settings.ADMIN_USERNAME}' не является администратором.",
                )

            password = getpass.getpass("Новый пароль: ")
            password_confirmation = getpass.getpass(
                "Повторите новый пароль: ",
            )

            if password != password_confirmation:
                raise RuntimeError("Пароли не совпадают.")

            use_case = ChangeEmployeePasswordUseCase(
                uow=_uow,
                password_service=password_service,
            )

            await use_case.execute(
                ChangeEmployeePasswordDTO(
                    actor_id=SYSTEM_ACTOR_ID,
                    employee_id=admin.employee_id,
                    password=password,
                ),
            )

    finally:
        await event_publisher.wait_pending()
        await postgres.dispose()

    print(
        f"Пароль администратора '{settings.ADMIN_USERNAME}' успешно изменён.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CLI управления Mountain Fairytale.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    admin_parser = subparsers.add_parser(
        "admin",
        help="Операции с администратором.",
    )

    admin_subparsers = admin_parser.add_subparsers(
        dest="admin_command",
        required=True,
    )

    admin_subparsers.add_parser(
        "change-password",
        help="Изменить пароль администратора.",
    )

    args = parser.parse_args()

    if args.command == "admin" and args.admin_command == "change-password":
        asyncio.run(change_admin_password())


if __name__ == "__main__":
    dotenv.load_dotenv()
    main()
