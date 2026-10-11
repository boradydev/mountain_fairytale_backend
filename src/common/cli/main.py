import argparse
import asyncio
import getpass

import dotenv

from src.common.domain.const import SYSTEM_ACTOR_ID
from src.common.infra.db.postgres.database import Postgres
from src.common.infra.services.password_service import PasswordService
from src.feat.employees.app.usecases.change_password import (
    ChangeEmployeePasswordDTO,
    ChangeEmployeePasswordUseCase,
)
from src.feat.employees.infra.employee_uow import EmployeesUOW


async def change_admin_password() -> None:
    postgres = Postgres()
    password_service = PasswordService()

    uow = EmployeesUOW(
        session_factory=postgres.session_factory,
    )

    try:
        async with uow as _uow:
            admin = await _uow.employees.get_admin()

            if admin is None:
                raise RuntimeError(
                    "Bootstrap-администратор не найден.",
                )

            if admin.role != "admin":
                raise RuntimeError(
                    "Учётная запись не является администратором.",
                )

            password = getpass.getpass("Новый пароль: ")
            password_confirmation = getpass.getpass(
                "Повторите новый пароль: ",
            )

            if password != password_confirmation:
                raise RuntimeError("Пароли не совпадают.")

            admin_id = admin.employee_id
            admin_username = admin.username

        use_case = ChangeEmployeePasswordUseCase(uow=uow, password_service=password_service)
        await use_case.execute(
            ChangeEmployeePasswordDTO(
                actor_id=SYSTEM_ACTOR_ID,
                employee_id=admin_id,
                password=password,
            ),
        )

    finally:
        await postgres.dispose()

    print(
        f"Пароль администратора '{admin_username}' успешно изменён.",
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
