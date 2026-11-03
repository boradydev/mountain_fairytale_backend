"""Allow anonymous pickup purchases and detach legacy placeholder clients."""

from alembic import op

from src.common.infra.db.postgres.alembic.migrations.sql_reader import sql_reader


revision = "82ac739e051d"
down_revision = "7b9d2c4a1e60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sql_reader("upgrade.sql", __file__))


def downgrade() -> None:
    op.execute(sql_reader("downgrade.sql", __file__))
