"""Create SubstituteUnavailability table

Revision ID: 0544876d0530
Revises: 8901b8e28b6f
Create Date: 2025-07-23 16:36:16.417559

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0544876d0530'
down_revision = '8901b8e28b6f'
branch_labels = None
depends_on = None


def upgrade():
    # Create SubstituteUnavailability table
    op.create_table('substitute_unavailability',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('all_day', sa.Boolean(), nullable=True, default=True),
        sa.Column('time_range', sa.String(length=50), nullable=True),
        sa.Column('repeat_pattern', sa.String(length=20), nullable=True),
        sa.Column('repeat_until', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='fk_substitute_unavailability_user_id'),
        sa.PrimaryKeyConstraint('id', name='pk_substitute_unavailability')
    )
    # Create index on user_id for faster lookups
    op.create_index('ix_substitute_unavailability_user_id', 'substitute_unavailability', ['user_id'], unique=False)
    # Create index on date for faster lookups
    op.create_index('ix_substitute_unavailability_date', 'substitute_unavailability', ['date'], unique=False)


def downgrade():
    # Drop SubstituteUnavailability table
    op.drop_index('ix_substitute_unavailability_date', table_name='substitute_unavailability')
    op.drop_index('ix_substitute_unavailability_user_id', table_name='substitute_unavailability')
    op.drop_table('substitute_unavailability')
