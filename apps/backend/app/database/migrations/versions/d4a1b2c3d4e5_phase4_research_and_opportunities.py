"""phase4_research_and_opportunities

Revision ID: d4a1b2c3d4e5
Revises: 993ea5da38e2
Create Date: 2026-11-20 20:45:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd4a1b2c3d4e5'
down_revision: Union[str, None] = '993ea5da38e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create research_records
    op.create_table(
        'research_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('source_url', sa.String(length=2048), nullable=True),
        sa.Column('source_name', sa.String(length=120), nullable=True),
        sa.Column('author', sa.String(length=120), nullable=True),
        sa.Column('source_quote', sa.Text(), nullable=True),
        sa.Column('observation_summary', sa.Text(), nullable=False),
        sa.Column('interpretation_notes', sa.Text(), nullable=True),
        sa.Column('evidence_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('collected_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'project_id', name='uq_research_records_id_project'),
        sa.CheckConstraint(
            "source_type IN ('user_interview', 'app_review', 'competitor_analysis', 'analytics', 'market_report', 'manual_observation')",
            name='ck_research_records_source_type',
        ),
    )
    op.create_index(op.f('ix_research_records_project_id'), 'research_records', ['project_id'], unique=False)
    op.create_index('ix_research_records_project_source_type', 'research_records', ['project_id', 'source_type'], unique=False)
    op.create_index('ix_research_records_project_collected_at', 'research_records', ['project_id', 'collected_at'], unique=False)

    # 2. Create growth_opportunities
    op.create_table(
        'growth_opportunities',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('slug', sa.String(length=220), nullable=False),
        sa.Column('problem_statement', sa.Text(), nullable=False),
        sa.Column('hypothesis', sa.Text(), nullable=False),
        sa.Column('proposed_mechanism', sa.Text(), nullable=False),
        sa.Column('target_audience', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='draft', nullable=False),
        sa.Column('estimated_impact', sa.String(length=20), server_default='medium', nullable=False),
        sa.Column('estimated_effort', sa.String(length=20), server_default='medium', nullable=False),
        sa.Column('confidence_score', sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column('priority', sa.String(length=20), server_default='p2_medium', nullable=False),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'project_id', name='uq_growth_opportunities_id_project'),
        sa.UniqueConstraint('project_id', 'slug', name='uq_growth_opportunities_project_slug'),
        sa.CheckConstraint(
            "category IN ('acquisition', 'activation', 'retention', 'referral', 'revenue', 'experimentation')",
            name='ck_growth_opportunities_category',
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'rejected', 'archived')",
            name='ck_growth_opportunities_status',
        ),
        sa.CheckConstraint(
            "estimated_impact IN ('low', 'medium', 'high', 'critical')",
            name='ck_growth_opportunities_estimated_impact',
        ),
        sa.CheckConstraint(
            "estimated_effort IN ('low', 'medium', 'high')",
            name='ck_growth_opportunities_estimated_effort',
        ),
        sa.CheckConstraint(
            "priority IN ('p0_urgent', 'p1_high', 'p2_medium', 'p3_low')",
            name='ck_growth_opportunities_priority',
        ),
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0.00 AND confidence_score <= 1.00)",
            name='ck_growth_opportunities_confidence',
        ),
    )
    op.create_index(op.f('ix_growth_opportunities_project_id'), 'growth_opportunities', ['project_id'], unique=False)
    op.create_index('ix_growth_opportunities_project_status', 'growth_opportunities', ['project_id', 'status'], unique=False)
    op.create_index('ix_growth_opportunities_project_category', 'growth_opportunities', ['project_id', 'category'], unique=False)
    op.create_index('ix_growth_opportunities_project_priority', 'growth_opportunities', ['project_id', 'priority'], unique=False)

    # 3. Create opportunity_status_history
    op.create_table(
        'opportunity_status_history',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('opportunity_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('previous_status', sa.String(length=30), nullable=True),
        sa.Column('new_status', sa.String(length=30), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('actor', sa.String(length=100), nullable=False),
        sa.Column('system_metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['opportunity_id', 'project_id'],
            ['growth_opportunities.id', 'growth_opportunities.project_id'],
            name='fk_history_opportunity_project',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "new_status IN ('draft', 'in_review', 'approved', 'rejected', 'archived')",
            name='ck_history_new_status',
        ),
        sa.CheckConstraint(
            "previous_status IS NULL OR previous_status IN ('draft', 'in_review', 'approved', 'rejected', 'archived')",
            name='ck_history_previous_status',
        ),
    )
    op.create_index('ix_opportunity_status_history_opp_created', 'opportunity_status_history', ['opportunity_id', 'created_at'], unique=False)
    op.create_index('ix_opportunity_status_history_project', 'opportunity_status_history', ['project_id', 'created_at'], unique=False)

    # 4. Create opportunity_research_associations
    op.create_table(
        'opportunity_research_associations',
        sa.Column('opportunity_id', sa.String(length=36), nullable=False),
        sa.Column('research_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['opportunity_id', 'project_id'],
            ['growth_opportunities.id', 'growth_opportunities.project_id'],
            name='fk_assoc_opportunity_project',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['research_id', 'project_id'],
            ['research_records.id', 'research_records.project_id'],
            name='fk_assoc_research_project',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('opportunity_id', 'research_id'),
    )
    op.create_index('ix_assoc_research_id', 'opportunity_research_associations', ['research_id'], unique=False)
    op.create_index('ix_assoc_project_id', 'opportunity_research_associations', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_table('opportunity_research_associations')
    op.drop_table('opportunity_status_history')
    op.drop_table('growth_opportunities')
    op.drop_table('research_records')
