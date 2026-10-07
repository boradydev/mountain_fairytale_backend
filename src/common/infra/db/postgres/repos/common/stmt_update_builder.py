from uuid import UUID

from sqlalchemy import column, table, update
from sqlalchemy.sql.expression import Update

from src.common.domain.events import FieldChange


class StmtUpdateBuilder:
    """Универсальный строитель SQL-выражений UPDATE для SQLAlchemy Core."""

    def __init__(
        self,
        table_name: str,
        id_column_name: str,
        allowed_columns: list[str],
    ) -> None:
        self._id_column_name = id_column_name

        # Разрешаем обновлять только переданные колонки + добавляем ID-колонку для фильтрации
        all_columns = set(allowed_columns) | {id_column_name}

        # Динамически создаем объект таблицы и распаковываем колонки через генератор
        self._table = table(table_name, *(column(col_name) for col_name in all_columns))

    def build_stmt(
        self,
        *,
        entity_id: UUID,
        changes: dict[str, FieldChange],
    ) -> Update:
        """Строит выражение UPDATE, фильтруя входящие изменения по разрешенным колонкам."""
        # Отбираем только те изменения, новые значения которых переданы
        values = {
            field_name: change.new
            for field_name, change in changes.items()
            if field_name in self._table.c
        }

        if not values:
            raise ValueError("No valid fields provided for update.")

        # Динамически получаем колонку ID через self._table.c[имя_строки]
        id_column = self._table.c[self._id_column_name]

        return update(self._table).where(id_column == entity_id).values(values)
