"""
empty message.

Revision ID: f8031806307b
Revises: e74dbe1c27eb
Create Date: 2026-10-01 09:21:13.807866

"""

from collections.abc import Sequence

from alembic import op

from src.infra.db.postgres.alembic.migrations.sql_reader import sql_reader


# revision identifiers, used by Alembic.
revision: str = "f8031806307b"
down_revision: str | Sequence[str] | None = "e74dbe1c27eb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(sql_reader("upgrade.sql", __file__))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sql_reader("downgrade.sql", __file__))
