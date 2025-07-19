# extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from twilio.rest import Client

db = SQLAlchemy()
mail = Mail()
twilio_client = None  # Will be initialized in app.py
twilio_initialized = False  # Flag to track if Twilio is initialized

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
