# extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from twilio.rest import Client

db = SQLAlchemy()
mail = Mail()
twilio_client = None  # Will be initialized in app.py
