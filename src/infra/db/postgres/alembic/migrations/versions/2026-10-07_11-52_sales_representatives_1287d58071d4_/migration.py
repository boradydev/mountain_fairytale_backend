"""empty message

Revision ID: 1287d58071d4
Revises: 0f573dc84b1f
Create Date: 2026-10-07 11:52:36.532355

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from src.infra.db.postgres.alembic.migrations.sql_reader import sql_reader


# revision identifiers, used by Alembic.
revision: str = '1287d58071d4'
down_revision: Union[str, Sequence[str], None] = '0f573dc84b1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(sql_reader("upgrade.sql", __file__))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sql_reader("downgrade.sql", __file__))
