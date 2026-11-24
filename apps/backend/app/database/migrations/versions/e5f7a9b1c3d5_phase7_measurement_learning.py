"""phase7_measurement_learning

Revision ID: e5f7a9b1c3d5
Revises: c9d3e5f7a9b2
Create Date: 2026-11-24 00:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e5f7a9b1c3d5'
down_revision: Union[str, None] = 'c9d3e5f7a9b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'experiments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('strategy_id', sa.String(length=36), nullable=False),
        sa.Column('goal_id', sa.String(length=36), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('hypothesis', sa.Text(), nullable=True),
        sa.Column('success_criteria_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['strategy_id', 'project_id'],
            ['growth_strategies.id', 'growth_strategies.project_id'],
            name='fk_experiments_strategy_project',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['goal_id', 'project_id'],
            ['strategy_goals.id', 'strategy_goals.project_id'],
            name='fk_experiments_goal_project',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'project_id', name='uq_experiments_id_project'),
        sa.CheckConstraint(
            "status IN ('draft', 'in_review', 'running', 'completed', 'cancelled')",
            name='ck_experiments_status',
        ),
    )
    op.create_index('ix_experiments_strategy_status', 'experiments', ['strategy_id', 'status'], unique=False)
    op.create_index('ix_experiments_project_status', 'experiments', ['project_id', 'status'], unique=False)
    op.create_index('ix_experiments_project_created', 'experiments', ['project_id', 'created_at'], unique=False)

    op.create_table(
        'experiment_status_history',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('experiment_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('previous_status', sa.String(length=30), nullable=True),
        sa.Column('new_status', sa.String(length=30), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('actor', sa.String(length=100), nullable=False),
        sa.Column('system_metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['experiment_id', 'project_id'],
            ['experiments.id', 'experiments.project_id'],
            name='fk_exp_history_experiment_project',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "new_status IN ('draft', 'in_review', 'running', 'completed', 'cancelled')",
            name='ck_exp_history_new_status',
        ),
        sa.CheckConstraint(
            "previous_status IS NULL OR previous_status IN ('draft', 'in_review', 'running', 'completed', 'cancelled')",
            name='ck_exp_history_previous_status',
        ),
    )
    op.create_index('ix_exp_history_experiment_created', 'experiment_status_history', ['experiment_id', 'created_at'], unique=False)
    op.create_index('ix_exp_history_project', 'experiment_status_history', ['project_id', 'created_at'], unique=False)

    op.create_table(
        'experiment_outcomes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('experiment_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column('sample_size', sa.Integer(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source', sa.String(length=30), nullable=False),
        sa.Column('source_ref', sa.String(length=200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('actor', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['experiment_id', 'project_id'],
            ['experiments.id', 'experiments.project_id'],
            name='fk_exp_outcome_experiment_project',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "source IN ('manual', 'integration', 'import')",
            name='ck_exp_outcome_source',
        ),
    )
    op.create_index('ix_exp_outcomes_experiment_created', 'experiment_outcomes', ['experiment_id', 'created_at'], unique=False)
    op.create_index('ix_exp_outcomes_project', 'experiment_outcomes', ['project_id', 'created_at'], unique=False)
    op.create_index('ix_exp_outcomes_metric', 'experiment_outcomes', ['experiment_id', 'metric_name'], unique=False)

    op.create_table(
        'experiment_evaluations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('experiment_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('verdict', sa.String(length=30), nullable=False),
        sa.Column('rationale_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actor', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['experiment_id', 'project_id'],
            ['experiments.id', 'experiments.project_id'],
            name='fk_exp_eval_experiment_project',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "verdict IN ('succeeded', 'inconclusive', 'failed')",
            name='ck_exp_eval_verdict',
        ),
    )
    op.create_index('ix_exp_evals_experiment_created', 'experiment_evaluations', ['experiment_id', 'created_at'], unique=False)
    op.create_index('ix_exp_evals_project', 'experiment_evaluations', ['project_id', 'created_at'], unique=False)

    op.create_table(
        'learning_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('strategy_id', sa.String(length=36), nullable=True),
        sa.Column('experiment_id', sa.String(length=36), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('insight', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('evidence_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('validated_by', sa.String(length=100), nullable=True),
        sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name='fk_learning_project', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['strategy_id', 'project_id'],
            ['growth_strategies.id', 'growth_strategies.project_id'],
            name='fk_learning_strategy_project',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['experiment_id', 'project_id'],
            ['experiments.id', 'experiments.project_id'],
            name='fk_learning_experiment_project',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'project_id', name='uq_learning_records_id_project'),
        sa.CheckConstraint(
            "status IN ('candidate', 'validated', 'rejected')",
            name='ck_learning_records_status',
        ),
    )
    op.create_index('ix_learning_records_project_status', 'learning_records', ['project_id', 'status'], unique=False)
    op.create_index('ix_learning_records_experiment', 'learning_records', ['experiment_id'], unique=False)
    op.create_index('ix_learning_records_project_id', 'learning_records', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_learning_records_project_id', table_name='learning_records')
    op.drop_index('ix_learning_records_experiment', table_name='learning_records')
    op.drop_index('ix_learning_records_project_status', table_name='learning_records')
    op.drop_table('learning_records')
    op.drop_index('ix_exp_evals_project', table_name='experiment_evaluations')
    op.drop_index('ix_exp_evals_experiment_created', table_name='experiment_evaluations')
    op.drop_table('experiment_evaluations')
    op.drop_index('ix_exp_outcomes_metric', table_name='experiment_outcomes')
    op.drop_index('ix_exp_outcomes_project', table_name='experiment_outcomes')
    op.drop_index('ix_exp_outcomes_experiment_created', table_name='experiment_outcomes')
    op.drop_table('experiment_outcomes')
    op.drop_index('ix_exp_history_project', table_name='experiment_status_history')
    op.drop_index('ix_exp_history_experiment_created', table_name='experiment_status_history')
    op.drop_table('experiment_status_history')
    op.drop_index('ix_experiments_project_created', table_name='experiments')
    op.drop_index('ix_experiments_project_status', table_name='experiments')
    op.drop_index('ix_experiments_strategy_status', table_name='experiments')
    op.drop_table('experiments')
