"""Create Organization table

Revision ID: fa696585b25c
Revises: e10cae9f58b6
Create Date: 2025-07-25 10:53:07.450152

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fa696585b25c'
down_revision = 'e10cae9f58b6'
branch_labels = None
depends_on = None


def upgrade():
    # Check if organization table exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    # Create organization table if it doesn't exist
    if 'organization' not in tables:
        op.create_table('organization',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
    
    # Check if "Point Arena Schools" organization exists
    result = conn.execute(sa.text("SELECT id FROM organization WHERE name = 'Point Arena Schools'")).fetchone()
    
    if result is None:
        # Create default "Point Arena Schools" organization
        conn.execute(sa.text("INSERT INTO organization (name) VALUES ('Point Arena Schools')"))
    
    # Get the default organization ID
    default_org_id = conn.execute(sa.text("SELECT id FROM organization WHERE name = 'Point Arena Schools'")).fetchone()[0]
    
    # Update users
    conn.execute(sa.text(f"UPDATE user SET organization_id = {default_org_id} WHERE organization_id IS NULL"))
    
    # Update schools
    conn.execute(sa.text(f"UPDATE school SET organization_id = {default_org_id} WHERE organization_id IS NULL"))
    
    # Update substitute requests
    conn.execute(sa.text(f"UPDATE substitute_request SET organization_id = {default_org_id} WHERE organization_id IS NULL"))


def downgrade():
    # Drop the organization table
    op.drop_table('organization')
