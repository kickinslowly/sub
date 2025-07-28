"""
Database migration management using Flask-Migrate and Alembic.
This module provides functions to initialize and manage database migrations.
"""
from flask_migrate import Migrate
from flask import Flask
from extensions import db
import os

# Initialize Flask-Migrate
migrate = Migrate()

def init_migrations(app: Flask):
    """
    Initialize Flask-Migrate with the Flask application.
    This creates the migrations directory if it doesn't exist.
    
    Args:
        app: The Flask application instance
    """
    # Initialize Flask-Migrate with the app and SQLAlchemy db
    migrate.init_app(app, db)
    
    # Create migrations directory if it doesn't exist
    migrations_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'migrations')
    if not os.path.exists(migrations_dir):
        os.makedirs(migrations_dir)
        print(f"Created migrations directory at {migrations_dir}")
    
    print("Flask-Migrate initialized successfully")

def create_migration_commands():
    """
    Instructions for creating and applying migrations.
    This is for documentation purposes.
    """
    return """
    # To create a migration (after model changes):
    flask db migrate -m "Description of changes"
    
    # To apply migrations:
    flask db upgrade
    
    # To rollback a migration:
    flask db downgrade
    
    # To see migration history:
    flask db history
    
    # To create an empty migration:
    flask db revision -m "Empty migration"
    """