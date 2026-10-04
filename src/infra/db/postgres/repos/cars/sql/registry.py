from uuid import UUID

from sqlalchemy import text
from sqlalchemy.sql.expression import Update

from src.domain.cars.entities import Car
from src.domain.common.events import FieldChange
from src.infra.db.postgres.repos.common.sql_reader import sql_reader
from src.infra.db.postgres.repos.common.stmt_update_builder import StmtUpdateBuilder


class CarSQL:
    """Контейнер SQL запросов и билдеров для сущности Car."""

    _updater = StmtUpdateBuilder(
        table_name="cars",
        id_column_name=Car.ID_FIELD,
        allowed_columns=list(Car.UPDATABLE_DATABASE_COLUMNS),
    )

    ADD = text(sql_reader("add.sql", __file__))
    GET_BY_ID = text(sql_reader("get_by_id.sql", __file__))
    GET_BY_NUMBER = text(sql_reader("get_by_number.sql", __file__))
    GET_ALL = text(sql_reader("get_all.sql", __file__))
    GET_ALL_WITH_DEACTIVATE = text(sql_reader("get_all_with_deactivated.sql", __file__))

    @classmethod
    def UPDATE(
        cls,
        *,
        car_id: UUID,
        changes: dict[str, FieldChange],
    ) -> Update:
        return cls._updater.build_stmt(
            entity_id=car_id,
            changes=changes,
        )
