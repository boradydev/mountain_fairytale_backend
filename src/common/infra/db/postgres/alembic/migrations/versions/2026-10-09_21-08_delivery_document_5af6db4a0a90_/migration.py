"""Delivery documents, points, items, and edit locks.

Revision ID: 5af6db4a0a90
Revises: 059030d3d021
Create Date: 2026-10-09 21:08:30.985816

"""
from typing import Sequence, Union

from alembic import op

from src.common.infra.db.postgres.alembic.migrations.sql_reader import sql_reader


revision: str = "5af6db4a0a90"
down_revision: Union[str, Sequence[str], None] = "059030d3d021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(sql_reader("upgrade.sql", __file__))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sql_reader("downgrade.sql", __file__))
