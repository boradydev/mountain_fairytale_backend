"""Preserve unsuccessful delivery attempts and their reasons."""

from alembic import op


revision = "b917ac56e024"
down_revision = "82ac739e051d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE points ADD COLUMN is_delivered boolean NOT NULL DEFAULT true")
    op.execute("ALTER TABLE points ADD COLUMN non_delivery_reason text NOT NULL DEFAULT ''")
    op.execute("""ALTER TABLE points ADD CONSTRAINT points_delivery_reason_check CHECK (
        (is_delivered AND non_delivery_reason = '') OR
        (NOT is_delivered AND length(trim(non_delivery_reason)) BETWEEN 1 AND 1000 AND client_id IS NOT NULL)
    )""")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM points WHERE NOT is_delivered) THEN
            RAISE EXCEPTION 'Restore unsuccessful deliveries before removing their state';
        END IF;
    END $$""")
    op.execute("ALTER TABLE points DROP CONSTRAINT points_delivery_reason_check")
    op.execute("ALTER TABLE points DROP COLUMN non_delivery_reason, DROP COLUMN is_delivered")
