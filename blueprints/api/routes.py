"""
API routes for the application.
"""
from flask import jsonify, request
from . import api_bp
import logging

logger = logging.getLogger(__name__)

@api_bp.route('/status')
def status():
    """
    API status endpoint.
    """
    return jsonify({"status": "ok"})