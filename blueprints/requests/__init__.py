from flask import Blueprint

requests_bp = Blueprint('requests', __name__, url_prefix='/requests')

from . import routes