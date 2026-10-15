"""Historical commission snapshots for delivery and pickup documents."""

from alembic import op

from src.common.infra.db.postgres.alembic.migrations.sql_reader import sql_reader


revision = "c8a2d91e470f"
down_revision = "5af6db4a0a90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sql_reader("upgrade.sql", __file__))


def downgrade() -> None:
    op.execute(sql_reader("downgrade.sql", __file__))
