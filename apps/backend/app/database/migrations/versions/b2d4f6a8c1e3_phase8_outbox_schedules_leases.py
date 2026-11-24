"""phase8 outbox, schedules, worker leases

Revision ID: b2d4f6a8c1e3
Revises: a1c3e5f7b9d2
Create Date: 2026-11-24

Adds transactional outbox events, persistent job schedules, and worker
lease columns on jobs for Phase 8 Milestone 2.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b2d4f6a8c1e3"
down_revision = "a1c3e5f7b9d2"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column("jobs", sa.Column("locked_by", sa.String(100), nullable=True))
    op.add_column(
        "jobs", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True)
    )

    op.create_table(
        "job_outbox_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_id", "project_id"],
            ["jobs.id", "jobs.project_id"],
            name="fk_job_outbox_job_project",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'published', 'failed')",
            name="ck_job_outbox_status",
        ),
    )
    op.create_index(
        "ix_job_outbox_status_created", "job_outbox_events", ["status", "created_at"]
    )
    op.create_index(
        "ix_job_outbox_project", "job_outbox_events", ["project_id", "created_at"]
    )

    op.create_table(
        "job_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("job_type", sa.String(100), nullable=False),
        sa.Column("payload_json", JSONB, nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("project_id", "name", name="uq_job_schedules_project_name"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_job_schedules_project",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("interval_seconds > 0", name="ck_job_schedules_interval"),
    )
    op.create_index("ix_job_schedules_due", "job_schedules", ["enabled", "next_run_at"])
    op.create_index("ix_job_schedules_project", "job_schedules", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_job_schedules_project", table_name="job_schedules")
    op.drop_index("ix_job_schedules_due", table_name="job_schedules")
    op.drop_table("job_schedules")
    op.drop_index("ix_job_outbox_project", table_name="job_outbox_events")
    op.drop_index("ix_job_outbox_status_created", table_name="job_outbox_events")
    op.drop_table("job_outbox_events")
    op.drop_column("jobs", "locked_until")
    op.drop_column("jobs", "locked_by")
