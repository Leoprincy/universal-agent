"""phase7 outcome supersession

Revision ID: b3d5f7a9c1e4
Revises: e5f7a9b1c3d5
Create Date: 2026-11-24

Adds supersedes_id to experiment_outcomes so a wrong observation can be
corrected by a new append-only record that references the superseded one.
The original observation is preserved; evaluation excludes superseded rows.
"""

from alembic import op
import sqlalchemy as sa


revision = "b3d5f7a9c1e4"
down_revision = "e5f7a9b1c3d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "experiment_outcomes",
        sa.Column("supersedes_id", sa.String(length=36), nullable=True),
    )
    op.create_unique_constraint(
        "uq_exp_outcomes_id_project", "experiment_outcomes", ["id", "project_id"]
    )
    op.create_foreign_key(
        "fk_exp_outcome_supersedes_project",
        "experiment_outcomes",
        "experiment_outcomes",
        ["supersedes_id", "project_id"],
        ["id", "project_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_exp_outcome_supersedes_project", "experiment_outcomes", type_="foreignkey"
    )
    op.drop_constraint(
        "uq_exp_outcomes_id_project", "experiment_outcomes", type_="unique"
    )
    op.drop_column("experiment_outcomes", "supersedes_id")
