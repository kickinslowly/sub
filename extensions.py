# extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from twilio.rest import Client
from authlib.integrations.flask_client import OAuth
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging

logger = logging.getLogger(__name__)

db = SQLAlchemy()
mail = Mail()
oauth = OAuth()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)
google = None  # Will be initialized in app.py
twilio_client = None  # Will be initialized in app.py
twilio_initialized = False  # Flag to track if Twilio is initialized

def init_google_oauth(app):
    """
    Initialize the Google OAuth client with the app configuration.
    """
    global google
    try:
        google = oauth.register(
            name='google',
            client_id=app.config['GOOGLE_CLIENT_ID'],
            client_secret=app.config['GOOGLE_CLIENT_SECRET'],
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            api_base_url='https://www.googleapis.com/oauth2/v1/',
            client_kwargs={
                'scope': 'openid email profile',
            },
        )
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Google OAuth client: {e}")
        return False

def init_twilio(account_sid, auth_token):
    """
    Initialize the Twilio client with the provided credentials.
    Returns True if successful, False otherwise.
    """
    global twilio_client, twilio_initialized
    try:
        if account_sid and auth_token:
            twilio_client = Client(account_sid, auth_token)
            twilio_initialized = True
            return True
        else:
            print("Twilio credentials are not properly configured.")
            return False
    except Exception as e:
        print(f"Failed to initialize Twilio client: {e}")
        return False
