"""
Request routes for the application.
"""
from flask import render_template, redirect, url_for, flash, request
from . import requests_bp
import logging

logger = logging.getLogger(__name__)

@requests_bp.route('/')
def index():
    """
    Requests index route.
    """
    return render_template('request.html')