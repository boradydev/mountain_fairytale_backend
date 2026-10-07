"""empty message

Revision ID: 82fffad694b2
Revises: 1287d58071d4
Create Date: 2026-10-07 12:44:05.989196

"""
from typing import Sequence, Union

from alembic import op

from src.common.infra.db.postgres.alembic.migrations.sql_reader import sql_reader

# revision identifiers, used by Alembic.
revision: str = '82fffad694b2'
down_revision: Union[str, Sequence[str], None] = '1287d58071d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(sql_reader("upgrade.sql", __file__))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sql_reader("downgrade.sql", __file__))
