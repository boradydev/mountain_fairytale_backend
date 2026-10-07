"""empty message

Revision ID: 0f573dc84b1f
Revises: 46ecdd8819a5
Create Date: 2026-10-07 10:28:12.111227

"""
from typing import Sequence, Union

from alembic import op

from src.common.infra.db.postgres.alembic.migrations.sql_reader import sql_reader

# revision identifiers, used by Alembic.
revision: str = '0f573dc84b1f'
down_revision: Union[str, Sequence[str], None] = '46ecdd8819a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(sql_reader("upgrade.sql", __file__))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sql_reader("downgrade.sql", __file__))
