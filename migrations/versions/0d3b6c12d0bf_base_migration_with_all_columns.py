"""Base migration with all columns

Revision ID: 0d3b6c12d0bf
Revises: 
Create Date: 2025-07-28 19:53:07.948386

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0d3b6c12d0bf'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create organization table
    try:
        op.create_table('organization',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
    except Exception as e:
        # Table might already exist, which is fine
        print(f"Note: {e}")
    
    # Create grade table
    try:
        op.create_table('grade',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=20), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
    except Exception as e:
        # Table might already exist, which is fine
        print(f"Note: {e}")
    
    # Create subject table
    try:
        op.create_table('subject',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=50), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
    except Exception as e:
        # Table might already exist, which is fine
        print(f"Note: {e}")
    
    # Create users table (with timezone column)
    try:
        op.create_table('users',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=True),
            sa.Column('email', sa.String(length=120), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False),
            sa.Column('phone', sa.String(length=20), nullable=True),
            sa.Column('timezone', sa.String(length=50), nullable=True, server_default='UTC'),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('organization_id', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
            sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
    except Exception as e:
        # Table might already exist, which is fine
        print(f"Note: {e}")
        
        # If the users table exists but doesn't have the timezone column, add it
        try:
            op.add_column('users', sa.Column('timezone', sa.String(length=50), nullable=True, server_default='UTC'))
            print("Added timezone column to existing users table")
        except Exception as e2:
            # Column might already exist, which is fine
            print(f"Note: {e2}")
    
    # Create school table
    try:
        op.create_table('school',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=50), nullable=False),
            sa.Column('code', sa.String(length=20), nullable=False),
            sa.Column('level1_admin_id', sa.Integer(), nullable=True),
            sa.Column('organization_id', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['level1_admin_id'], ['users.id'], ),
            sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
    except Exception as e:
        # Table might already exist, which is fine
        print(f"Note: {e}")
    
    # Create substitute_unavailability table
    try:
        op.create_table('substitute_unavailability',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('date', sa.Date(), nullable=False),
            sa.Column('all_day', sa.Boolean(), nullable=True),
            sa.Column('time_range', sa.String(length=50), nullable=True),
            sa.Column('repeat_pattern', sa.String(length=20), nullable=True),
            sa.Column('repeat_until', sa.Date(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
    except Exception as e:
        # Table might already exist, which is fine
        print(f"Note: {e}")
    
    # Create substitute_request table
    try:
        op.create_table('substitute_request',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('teacher_id', sa.Integer(), nullable=False),
            sa.Column('date', sa.Date(), nullable=False),
            sa.Column('time', sa.String(length=50), nullable=False),
            sa.Column('details', sa.Text(), nullable=True),
            sa.Column('reason', sa.String(length=20), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('substitute_id', sa.Integer(), nullable=True),
            sa.Column('grade_id', sa.Integer(), nullable=True),
            sa.Column('subject_id', sa.Integer(), nullable=True),
            sa.Column('school_id', sa.Integer(), nullable=True),
            sa.Column('organization_id', sa.Integer(), nullable=True),
            sa.Column('token', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['grade_id'], ['grade.id'], ),
            sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
            sa.ForeignKeyConstraint(['school_id'], ['school.id'], ),
            sa.ForeignKeyConstraint(['subject_id'], ['subject.id'], ),
            sa.ForeignKeyConstraint(['substitute_id'], ['users.id'], ),
            sa.ForeignKeyConstraint(['teacher_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('token')
        )
    except Exception as e:
        # Table might already exist, which is fine
        print(f"Note: {e}")
    
    # Create association tables for many-to-many relationships
    try:
        op.create_table('user_grades',
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('grade_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['grade_id'], ['grade.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('user_id', 'grade_id')
        )
    except Exception as e:
        # Table might already exist, which is fine
        print(f"Note: {e}")
    
    try:
        op.create_table('user_schools',
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('school_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['school_id'], ['school.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('user_id', 'school_id')
        )
    except Exception as e:
        # Table might already exist, which is fine
        print(f"Note: {e}")
    
    try:
        op.create_table('user_subjects',
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('subject_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['subject_id'], ['subject.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('user_id', 'subject_id')
        )
    except Exception as e:
        # Table might already exist, which is fine
        print(f"Note: {e}")


def downgrade():
    # Drop tables in reverse order of creation
    try:
        op.drop_table('user_subjects')
    except Exception as e:
        print(f"Note: {e}")
    
    try:
        op.drop_table('user_schools')
    except Exception as e:
        print(f"Note: {e}")
    
    try:
        op.drop_table('user_grades')
    except Exception as e:
        print(f"Note: {e}")
    
    try:
        op.drop_table('substitute_request')
    except Exception as e:
        print(f"Note: {e}")
    
    try:
        op.drop_table('substitute_unavailability')
    except Exception as e:
        print(f"Note: {e}")
    
    try:
        op.drop_table('school')
    except Exception as e:
        print(f"Note: {e}")
    
    try:
        op.drop_table('users')
    except Exception as e:
        print(f"Note: {e}")
    
    try:
        op.drop_table('subject')
    except Exception as e:
        print(f"Note: {e}")
    
    try:
        op.drop_table('grade')
    except Exception as e:
        print(f"Note: {e}")
    
    try:
        op.drop_table('organization')
    except Exception as e:
        print(f"Note: {e}")
