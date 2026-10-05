from uuid import UUID

from sqlalchemy import text
from sqlalchemy.sql.expression import Update

from src.domain.common.events import FieldChange
from src.domain.employees.employee_entities import Employee
from src.infra.db.postgres.repos.common.sql_reader import sql_reader
from src.infra.db.postgres.repos.common.stmt_update_builder import StmtUpdateBuilder


class EmployeeSQL:
    """Контейнер SQL запросов и билдеров для сущности Employee."""

    # Инициализируем билдер один раз на уровне класса через композицию
    _updater = StmtUpdateBuilder(
        table_name="employees",
        id_column_name=Employee.ID_FIELD,
        # Передаем список, который за декларирован в самом Домене:
        allowed_columns=list(Employee.UPDATABLE_DATABASE_COLUMNS),
    )

    # Статические сырые запросы
    ADD = text(sql_reader("add.sql", __file__))
    GET_BY_ID = text(sql_reader("get_by_id.sql", __file__))
    GET_BY_USERNAME = text(sql_reader("get_by_username.sql", __file__))
    GET_ALL = text(sql_reader("get_all.sql", __file__))

    @classmethod
    def UPDATE(
        cls,
        *,
        employee_id: UUID,
        changes: dict[str, FieldChange],
    ) -> Update:
        # Делегируем построение запроса нашему универсальному билдеру
        return cls._updater.build_stmt(
            entity_id=employee_id,
            changes=changes,
        )
