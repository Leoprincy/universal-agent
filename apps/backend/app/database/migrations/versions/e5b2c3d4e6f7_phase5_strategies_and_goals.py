"""phase5_strategies_and_goals

Revision ID: e5b2c3d4e6f7
Revises: d4a1b2c3d4e5
Create Date: 2026-11-20 22:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e5b2c3d4e6f7'
down_revision: Union[str, None] = 'd4a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create growth_strategies
    op.create_table(
        'growth_strategies',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('slug', sa.String(length=220), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('strategic_vision', sa.Text(), nullable=False),
        sa.Column('target_audience', sa.Text(), nullable=False),
        sa.Column('strategic_constraints', sa.Text(), nullable=True),
        sa.Column('budget_envelope', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('currency', sa.String(length=3), server_default='USD', nullable=False),
        sa.Column('time_horizon', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='draft', nullable=False),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'project_id', name='uq_growth_strategies_id_project'),
        sa.UniqueConstraint('project_id', 'slug', name='uq_growth_strategies_project_slug'),
        sa.CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'active', 'completed', 'archived')",
            name='ck_growth_strategies_status',
        ),
        sa.CheckConstraint(
            "budget_envelope IS NULL OR budget_envelope >= 0.00",
            name='ck_growth_strategies_budget',
        ),
        sa.CheckConstraint(
            "length(currency) = 3",
            name='ck_growth_strategies_currency',
        ),
    )
    op.create_index(op.f('ix_growth_strategies_project_id'), 'growth_strategies', ['project_id'], unique=False)
    op.create_index('ix_growth_strategies_project_status', 'growth_strategies', ['project_id', 'status'], unique=False)
    op.create_index('ix_growth_strategies_project_time_horizon', 'growth_strategies', ['project_id', 'time_horizon'], unique=False)

    # 2. Create strategy_goals
    op.create_table(
        'strategy_goals',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('strategy_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('metric_unit', sa.String(length=50), nullable=False),
        sa.Column('baseline_value', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('current_value', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('target_value', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='pending', nullable=False),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['strategy_id', 'project_id'],
            ['growth_strategies.id', 'growth_strategies.project_id'],
            name='fk_strategy_goals_strategy_project',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'project_id', name='uq_strategy_goals_id_project'),
        sa.CheckConstraint(
            "status IN ('pending', 'on_track', 'at_risk', 'behind', 'achieved', 'abandoned')",
            name='ck_strategy_goals_status',
        ),
    )
    op.create_index(op.f('ix_strategy_goals_strategy_id'), 'strategy_goals', ['strategy_id'], unique=False)
    op.create_index('ix_strategy_goals_strategy_status', 'strategy_goals', ['strategy_id', 'status'], unique=False)
    op.create_index('ix_strategy_goals_project_status', 'strategy_goals', ['project_id', 'status'], unique=False)

    # 3. Create strategy_opportunity_associations
    op.create_table(
        'strategy_opportunity_associations',
        sa.Column('strategy_id', sa.String(length=36), nullable=False),
        sa.Column('opportunity_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('strategic_rationale', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['strategy_id', 'project_id'],
            ['growth_strategies.id', 'growth_strategies.project_id'],
            name='fk_assoc_strat_strategy_project',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['opportunity_id', 'project_id'],
            ['growth_opportunities.id', 'growth_opportunities.project_id'],
            name='fk_assoc_strat_opportunity_project',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('strategy_id', 'opportunity_id'),
    )
    op.create_index('ix_assoc_strat_opportunity_id', 'strategy_opportunity_associations', ['opportunity_id'], unique=False)
    op.create_index('ix_assoc_strat_project_id', 'strategy_opportunity_associations', ['project_id'], unique=False)

    # 4. Create strategy_status_history
    op.create_table(
        'strategy_status_history',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('strategy_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('previous_status', sa.String(length=30), nullable=True),
        sa.Column('new_status', sa.String(length=30), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('actor', sa.String(length=100), nullable=False),
        sa.Column('system_metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['strategy_id', 'project_id'],
            ['growth_strategies.id', 'growth_strategies.project_id'],
            name='fk_strat_history_strategy_project',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "new_status IN ('draft', 'in_review', 'approved', 'active', 'completed', 'archived')",
            name='ck_strategy_history_new_status',
        ),
        sa.CheckConstraint(
            "previous_status IS NULL OR previous_status IN ('draft', 'in_review', 'approved', 'active', 'completed', 'archived')",
            name='ck_strategy_history_previous_status',
        ),
    )
    op.create_index('ix_strategy_status_history_strat_created', 'strategy_status_history', ['strategy_id', 'created_at'], unique=False)
    op.create_index('ix_strategy_status_history_project', 'strategy_status_history', ['project_id', 'created_at'], unique=False)

    # 5. Create goal_metric_updates
    op.create_table(
        'goal_metric_updates',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('goal_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('previous_value', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('new_value', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('actor', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['goal_id', 'project_id'],
            ['strategy_goals.id', 'strategy_goals.project_id'],
            name='fk_metric_update_goal_project',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_goal_metric_updates_goal_created', 'goal_metric_updates', ['goal_id', 'created_at'], unique=False)
    op.create_index('ix_goal_metric_updates_project', 'goal_metric_updates', ['project_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('goal_metric_updates')
    op.drop_table('strategy_status_history')
    op.drop_table('strategy_opportunity_associations')
    op.drop_table('strategy_goals')
    op.drop_table('growth_strategies')
