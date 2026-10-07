"""empty message

Revision ID: 9b4a134cedfa
Revises: f8031806307b
Create Date: 2026-10-02 18:00:11.285264

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from src.infra.db.postgres.alembic.migrations.sql_reader import sql_reader

# revision identifiers, used by Alembic.
revision: str = '9b4a134cedfa'
down_revision: Union[str, Sequence[str], None] = 'f8031806307b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(sql_reader("upgrade.sql", __file__))



def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sql_reader("downgrade.sql", __file__))

