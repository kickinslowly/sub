"""
Super Admin blueprint for the application.
This blueprint handles all super admin functionality.
"""
from flask import Blueprint

# Create the blueprint
super_admin_bp = Blueprint('super_admin', __name__, url_prefix='/super_admin')

# Import routes at the end to avoid circular imports
from . import routes