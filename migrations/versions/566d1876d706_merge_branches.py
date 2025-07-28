"""Merge branches

Revision ID: 566d1876d706
Revises: 0544876d0530, drop_campus_column
Create Date: 2025-07-24 19:09:49.183493

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '566d1876d706'
down_revision = ('0544876d0530', 'drop_campus_column')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
