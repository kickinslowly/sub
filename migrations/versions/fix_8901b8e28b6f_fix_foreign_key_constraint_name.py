"""Fix foreign key constraint name

Revision ID: fix_8901b8e28b6f
Revises: 566d1876d706
Create Date: 2025-07-24 19:10:08.352684

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_8901b8e28b6f'
down_revision = '566d1876d706'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
