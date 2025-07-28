"""Drop campus column from user table

Revision ID: drop_campus_column
Revises: 8901b8e28b6f
Create Date: 2025-07-24 18:18:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'drop_campus_column'
down_revision = '8901b8e28b6f'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the campus column from the user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('campus')


def downgrade():
    # Add the campus column back to the user table if needed
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('campus', sa.VARCHAR(length=20), nullable=True))