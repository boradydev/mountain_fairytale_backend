from typing import Any

import sqlparse
from sqlalchemy import Delete, Insert, Select, Update
from sqlalchemy.ext.asyncio import create_async_engine


engine = create_async_engine("postgresql+asyncpg://")

StmtType = Select[Any] | Update | Insert | Delete


def stmt_debug(stmt: StmtType) -> str:
    """
    Компилирует SQLAlchemy-выражение в отформатированный, читаемый ИИ
    SQL-запрос в формате Markdown с подставленными значениями.
    """
    # 1. Компилируем выражение с подстановкой реальных значений (literal_binds)
    raw_sql = str(
        stmt.compile(
            dialect=engine.dialect,
            compile_kwargs={"literal_binds": True}
        )
    )

    # 2. Красиво форматируем SQL запрос (делаем переносы и отступы)
    try:
        formatted_sql = sqlparse.format(
            raw_sql,
            reindent=True,
            keyword_case='upper'
        )
    except ImportError:
        # Запасной вариант, если sqlparse не установлен
        formatted_sql = raw_sql

    # 3. Оборачиваем в Markdown для идеального отображения в чатах с ИИ
    ai_friendly_output = (
        "\n### Generated SQL for Analysis:\n"
        "```sql\n"
        f"{formatted_sql.strip()}\n"
        "```\n"
    )

    return ai_friendly_output
