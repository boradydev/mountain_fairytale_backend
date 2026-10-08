"""empty message

Revision ID: 059030d3d021
Revises: 82fffad694b2
Create Date: 2026-10-08 18:49:18.591617

"""
from typing import Sequence, Union

from alembic import op

from src.common.infra.db.postgres.alembic.migrations.sql_reader import sql_reader


# revision identifiers, used by Alembic.
revision: str = "059030d3d021"
down_revision: Union[str, Sequence[str], None] = "82fffad694b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(sql_reader("upgrade.sql", __file__))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sql_reader("downgrade.sql", __file__))
