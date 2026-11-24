"""phase8 persistent job infrastructure

Revision ID: a1c3e5f7b9d2
Revises: e7f9a1b3c5d7
Create Date: 2026-11-24

Creates jobs (durable source of truth) and job_events (append-only lifecycle
audit) for Phase 8 background task orchestration.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a1c3e5f7b9d2"
down_revision = "e7f9a1b3c5d7"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("job_type", sa.String(100), nullable=False),
        sa.Column("payload_json", JSONB, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(200), nullable=True),
        sa.Column("correlation_id", sa.String(100), nullable=True),
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
        sa.UniqueConstraint("id", "project_id", name="uq_jobs_id_project"),
        sa.UniqueConstraint(
            "project_id", "idempotency_key", name="uq_jobs_project_idempotency"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_jobs_project", ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_jobs_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_jobs_attempt_count"),
        sa.CheckConstraint("max_attempts > 0", name="ck_jobs_max_attempts"),
    )
    op.create_index("ix_jobs_project_status", "jobs", ["project_id", "status"])
    op.create_index("ix_jobs_project_created", "jobs", ["project_id", "created_at"])
    op.create_index("ix_jobs_dispatch", "jobs", ["status", "scheduled_at"])
    op.create_index("ix_jobs_job_type", "jobs", ["job_type"])

    op.create_table(
        "job_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("job_id", "seq", name="uq_job_events_job_seq"),
        sa.ForeignKeyConstraint(
            ["job_id", "project_id"],
            ["jobs.id", "jobs.project_id"],
            name="fk_job_events_job_project",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "event_type IN ('created', 'queued', 'started', 'completed', 'failed', 'cancelled', 'requeued')",
            name="ck_job_events_type",
        ),
    )
    op.create_index("ix_job_events_job_seq", "job_events", ["job_id", "seq"])
    op.create_index("ix_job_events_project", "job_events", ["project_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_job_events_project", table_name="job_events")
    op.drop_index("ix_job_events_job_seq", table_name="job_events")
    op.drop_table("job_events")
    op.drop_index("ix_jobs_job_type", table_name="jobs")
    op.drop_index("ix_jobs_dispatch", table_name="jobs")
    op.drop_index("ix_jobs_project_created", table_name="jobs")
    op.drop_index("ix_jobs_project_status", table_name="jobs")
    op.drop_table("jobs")
