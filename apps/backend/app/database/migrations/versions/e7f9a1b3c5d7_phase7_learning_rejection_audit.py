"""phase7 learning rejection audit fields

Revision ID: e7f9a1b3c5d7
Revises: d2e4f6a8c0b3
Create Date: 2026-11-24

Adds rejected_by/rejected_at to learning_records so rejections preserve the
same actor/timestamp audit trail as validations.
"""

from alembic import op
import sqlalchemy as sa


revision = "e7f9a1b3c5d7"
down_revision = "d2e4f6a8c0b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "learning_records",
        sa.Column("rejected_by", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "learning_records",
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("learning_records", "rejected_at")
    op.drop_column("learning_records", "rejected_by")
