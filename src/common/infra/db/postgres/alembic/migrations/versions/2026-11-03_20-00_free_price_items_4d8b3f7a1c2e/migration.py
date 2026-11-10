"""Add catalog free-price flag and route item driver note."""

from alembic import op

from src.common.infra.db.postgres.alembic.migrations.sql_reader import sql_reader


revision = "4d8b3f7a1c2e"
down_revision = "f61da2e3b780"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sql_reader("upgrade.sql", __file__))


def downgrade() -> None:
    op.execute(sql_reader("downgrade.sql", __file__))
