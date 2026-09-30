from typing import Any

from sqlalchemy import column, table, text, update, UUID
from sqlalchemy.sql import Executable

from src.domain.common.events import FieldChange
from src.infra.db.postgres.repos.common.sql_reader import sql_reader


class SQL:
    _EMPLOYEES = table(
        "employees",
        column("employee_id"),
        column("username"),
        column("password_hash"),
        column("is_active"),
    )

    ADD = text(sql_reader("add.sql", __file__))
    GET_BY_ID = text(sql_reader("get_by_id.sql", __file__))
    GET_ALL = text(sql_reader("get_all.sql", __file__))

    @staticmethod
    def UPDATE(
        *,
        employee_id: UUID,
        changes: dict[str, FieldChange],
    ) -> Executable:
        values = {
            field_name: change.new
            for field_name, change in changes.items()
        }

        return (
            update(SQL._EMPLOYEES)
            .where(
                SQL._EMPLOYEES.c.employee_id == employee_id,
            )
            .values(values)
        )