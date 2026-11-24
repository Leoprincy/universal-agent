"""goal_status_history

Revision ID: f7a1b2c3d4e5
Revises: e5b2c3d4e6f7
Create Date: 2026-11-23 18:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f7a1b2c3d4e5'
down_revision: Union[str, None] = 'e5b2c3d4e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'goal_status_history',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('goal_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('previous_status', sa.String(length=30), nullable=True),
        sa.Column('new_status', sa.String(length=30), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('actor', sa.String(length=100), nullable=False),
        sa.Column('system_metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['goal_id', 'project_id'],
            ['strategy_goals.id', 'strategy_goals.project_id'],
            name='fk_goal_history_goal_project',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "new_status IN ('pending', 'on_track', 'at_risk', 'behind', 'achieved', 'abandoned')",
            name='ck_goal_history_new_status',
        ),
        sa.CheckConstraint(
            "previous_status IS NULL OR previous_status IN ('pending', 'on_track', 'at_risk', 'behind', 'achieved', 'abandoned')",
            name='ck_goal_history_previous_status',
        ),
    )
    op.create_index('ix_goal_status_history_goal_created', 'goal_status_history', ['goal_id', 'created_at'], unique=False)
    op.create_index('ix_goal_status_history_project', 'goal_status_history', ['project_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_goal_status_history_project', table_name='goal_status_history')
    op.drop_index('ix_goal_status_history_goal_created', table_name='goal_status_history')
    op.drop_table('goal_status_history')
