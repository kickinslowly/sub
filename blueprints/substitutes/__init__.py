from flask import Blueprint

substitutes_bp = Blueprint('substitutes', __name__, url_prefix='/substitutes')

from . import routes