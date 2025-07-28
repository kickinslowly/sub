"""
Admin routes for the application.
"""
from flask import render_template, redirect, url_for, flash, request
from . import admin_bp
import logging

logger = logging.getLogger(__name__)

@admin_bp.route('/')
def index():
    """
    Admin dashboard index route.
    """
    return render_template('admin_dashboard.html')