"""Give document rows stable identity and permit repeated free-price products."""

from alembic import op

from src.common.infra.db.postgres.alembic.migrations.sql_reader import sql_reader


revision = "7d1f4e09ac32"
down_revision = "4d8b3f7a1c2e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sql_reader("upgrade.sql", __file__))


def downgrade() -> None:
    op.execute(sql_reader("downgrade.sql", __file__))
