"""empty message

Revision ID: e74dbe1c27eb
Revises: e7dc382495aa
Create Date: 2026-09-30 19:02:58.134268

"""
from typing import Sequence, Union

from alembic import op

from src.infra.db.postgres.alembic.migrations.sql_reader import sql_reader

# revision identifiers, used by Alembic.
revision: str = 'e74dbe1c27eb'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(sql_reader("upgrade.sql", __file__))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sql_reader("downgrade.sql", __file__))
