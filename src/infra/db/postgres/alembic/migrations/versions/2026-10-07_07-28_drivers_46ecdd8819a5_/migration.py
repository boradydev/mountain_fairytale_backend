"""empty message

Revision ID: 46ecdd8819a5
Revises: 9b4a134cedfa
Create Date: 2026-10-07 07:28:40.770400

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from src.infra.db.postgres.alembic.migrations.sql_reader import sql_reader


# revision identifiers, used by Alembic.
revision: str = '46ecdd8819a5'
down_revision: Union[str, Sequence[str], None] = '9b4a134cedfa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(sql_reader("upgrade.sql", __file__))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sql_reader("downgrade.sql", __file__))
