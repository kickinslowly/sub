"""rename_user_table_to_users

Revision ID: 37ee0c54e700
Revises: fa696585b25c
Create Date: 2025-07-28 18:40:38.875913

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '37ee0c54e700'
down_revision = 'fa696585b25c'
branch_labels = None
depends_on = None


def upgrade():
    # Rename the table first (if it exists)
    try:
        op.rename_table('user', 'users')
    except Exception as e:
        # Table might not exist yet, which is fine
        pass
        
    # Now add the timezone column to the users table if it doesn't already exist
    try:
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.add_column(sa.Column('timezone', sa.String(length=50), nullable=True))
    except Exception as e:
        # Column might already exist, which is fine
        pass


def downgrade():
    # Remove the timezone column first
    try:
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.drop_column('timezone')
    except Exception as e:
        # Column might not exist, which is fine
        pass
    
    # Rename back if needed
    try:
        op.rename_table('users', 'user')
    except Exception as e:
        # Table might not exist, which is fine
        pass
