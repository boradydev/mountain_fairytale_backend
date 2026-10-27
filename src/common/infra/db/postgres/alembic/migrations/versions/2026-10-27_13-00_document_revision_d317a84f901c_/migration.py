"""Version delivery documents and identify interrupted saves."""

import sqlalchemy as sa
from alembic import op


revision = "d317a84f901c"
down_revision = "c8a2d91e470f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("delivery_documents", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("delivery_documents", sa.Column("last_operation_id", sa.UUID(), nullable=True))
    op.add_column("delivery_documents", sa.Column("creation_request_id", sa.UUID(), nullable=True))
    op.add_column("delivery_documents", sa.Column("creation_request_hash", sa.Text(), nullable=True))
    op.create_check_constraint("delivery_documents_revision_check", "delivery_documents", "revision >= 1")
    op.create_unique_constraint(
        "uq_delivery_documents_creation_request_id", "delivery_documents", ["creation_request_id"]
    )


def downgrade() -> None:
    op.drop_constraint("delivery_documents_revision_check", "delivery_documents", type_="check")
    op.drop_constraint("uq_delivery_documents_creation_request_id", "delivery_documents", type_="unique")
    op.drop_column("delivery_documents", "creation_request_id")
    op.drop_column("delivery_documents", "creation_request_hash")
    op.drop_column("delivery_documents", "last_operation_id")
    op.drop_column("delivery_documents", "revision")
