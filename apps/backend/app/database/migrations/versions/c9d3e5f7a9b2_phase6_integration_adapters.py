"""phase6_integration_adapters

Revision ID: c9d3e5f7a9b2
Revises: f7a1b2c3d4e5
Create Date: 2026-11-23 20:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c9d3e5f7a9b2'
down_revision: Union[str, None] = 'f7a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'integration_providers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('adapter_type', sa.String(length=50), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('sandbox_only', sa.Boolean(), nullable=False),
        sa.Column('rate_limit_per_minute', sa.Integer(), nullable=False),
        sa.Column('config_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name='fk_integration_provider_project', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'name', name='uq_integration_provider_project_name'),
        sa.UniqueConstraint('id', 'project_id', name='uq_integration_provider_id_project'),
        sa.CheckConstraint('rate_limit_per_minute > 0', name='ck_integration_provider_rate_limit'),
    )
    op.create_index('ix_integration_providers_project', 'integration_providers', ['project_id', 'created_at'], unique=False)

    op.create_table(
        'integration_credentials',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('provider_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('ciphertext', sa.Text(), nullable=False),
        sa.Column('key_version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['provider_id', 'project_id'],
            ['integration_providers.id', 'integration_providers.project_id'],
            name='fk_credential_provider_project',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_id', name='uq_integration_credential_provider'),
    )

    op.create_table(
        'integration_actions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('provider_id', sa.String(length=36), nullable=False),
        sa.Column('action_type', sa.String(length=100), nullable=False),
        sa.Column('payload_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('payload_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('idempotency_key', sa.String(length=200), nullable=True),
        sa.Column('actor', sa.String(length=100), nullable=False),
        sa.Column('approver', sa.String(length=100), nullable=True),
        sa.Column('decision_reason', sa.Text(), nullable=True),
        sa.Column('pending_approval_expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('approval_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False),
        sa.Column('result_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['provider_id', 'project_id'],
            ['integration_providers.id', 'integration_providers.project_id'],
            name='fk_action_provider_project',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_id', 'idempotency_key', name='uq_integration_action_idempotency'),
        sa.UniqueConstraint('id', 'project_id', name='uq_integration_action_id_project'),
        sa.CheckConstraint(
            "status IN ('pending_approval', 'approved', 'rejected', 'expired', 'executing', 'succeeded', 'failed', 'cancelled')",
            name='ck_integration_action_status',
        ),
    )
    op.create_index('ix_integration_actions_project_status', 'integration_actions', ['project_id', 'status'], unique=False)
    op.create_index('ix_integration_actions_provider_status', 'integration_actions', ['provider_id', 'status'], unique=False)

    op.create_table(
        'integration_action_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('action_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('actor', sa.String(length=100), nullable=False),
        sa.Column('detail_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['action_id', 'project_id'],
            ['integration_actions.id', 'integration_actions.project_id'],
            name='fk_action_event_action_project',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_integration_action_events_action', 'integration_action_events', ['action_id', 'created_at'], unique=False)
    op.create_index('ix_integration_action_events_project', 'integration_action_events', ['project_id', 'created_at'], unique=False)

    op.create_table(
        'integration_call_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('action_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('provider_id', sa.String(length=36), nullable=False),
        sa.Column('attempt', sa.Integer(), nullable=False),
        sa.Column('mode', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('response_status', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['action_id', 'project_id'],
            ['integration_actions.id', 'integration_actions.project_id'],
            name='fk_call_log_action_project',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("mode IN ('sandbox', 'live')", name='ck_call_log_mode'),
    )
    op.create_index('ix_integration_call_logs_action', 'integration_call_logs', ['action_id', 'created_at'], unique=False)
    op.create_index('ix_integration_call_logs_provider_created', 'integration_call_logs', ['provider_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_integration_call_logs_provider_created', table_name='integration_call_logs')
    op.drop_index('ix_integration_call_logs_action', table_name='integration_call_logs')
    op.drop_table('integration_call_logs')
    op.drop_index('ix_integration_action_events_project', table_name='integration_action_events')
    op.drop_index('ix_integration_action_events_action', table_name='integration_action_events')
    op.drop_table('integration_action_events')
    op.drop_index('ix_integration_actions_provider_status', table_name='integration_actions')
    op.drop_index('ix_integration_actions_project_status', table_name='integration_actions')
    op.drop_table('integration_actions')
    op.drop_table('integration_credentials')
    op.drop_index('ix_integration_providers_project', table_name='integration_providers')
    op.drop_table('integration_providers')
