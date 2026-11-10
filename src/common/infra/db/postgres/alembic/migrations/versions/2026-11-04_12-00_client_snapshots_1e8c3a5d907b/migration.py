"""Capture historical client details on delivery points."""

from alembic import op

from src.common.infra.db.postgres.alembic.migrations.sql_reader import sql_reader


revision = "1e8c3a5d907b"
down_revision = "7d1f4e09ac32"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sql_reader("upgrade.sql", __file__))


def downgrade() -> None:
    op.execute(sql_reader("downgrade.sql", __file__))
