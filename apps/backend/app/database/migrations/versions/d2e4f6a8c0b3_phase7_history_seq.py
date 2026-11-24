"""phase7 experiment history sequence

Revision ID: d2e4f6a8c0b3
Revises: b3d5f7a9c1e4
Create Date: 2026-11-24

Adds a per-experiment monotonic seq to experiment_status_history so audit
ordering is deterministic even when created_at values tie.
"""

from alembic import op
import sqlalchemy as sa


revision = "d2e4f6a8c0b3"
down_revision = "b3d5f7a9c1e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "experiment_status_history",
        sa.Column("seq", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_exp_history_experiment_seq",
        "experiment_status_history",
        ["experiment_id", "seq"],
    )
    op.create_unique_constraint(
        "uq_exp_history_exp_seq",
        "experiment_status_history",
        ["experiment_id", "seq"],
    )
    # Backfill existing rows deterministically by created_at then id.
    op.execute(
        """
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY experiment_id ORDER BY created_at, id
            ) AS rn
            FROM experiment_status_history
        )
        UPDATE experiment_status_history h
        SET seq = ranked.rn
        FROM ranked
        WHERE h.id = ranked.id
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_exp_history_exp_seq", "experiment_status_history", type_="unique"
    )
    op.drop_index(
        "ix_exp_history_experiment_seq", table_name="experiment_status_history"
    )
    op.drop_column("experiment_status_history", "seq")
