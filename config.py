import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class Config:
    # Use environment variables with fallbacks for sensitive information
    SECRET_KEY = os.environ.get('SECRET_KEY', 'f8ff728627036ae23e1c0b0dd02b3a69f0933da51b3493bb1d0d95cda12daff8')

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///portal.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Google OAuth credentials
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '584875541165-6b95b2d7k5vlbs7ebqmpu8md94k2q4k5.apps.googleusercontent.com')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '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')

    # Email configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'kickinslowly@gmail.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'suwj zxyj xiwt vozh')

    # Tech coordinator emails (highest level admin)
    TECH_COORDINATOR_EMAILS = os.environ.get('TECH_COORDINATOR_EMAILS', 'kickinslowly@gmail.com').split(',')
    
    # Admin emails (level 2 admins - front office, principal)
    ADMIN_EMAILS = os.environ.get('ADMIN_EMAILS', 'placeholder@gmail.com').split(',')

    # Twilio configuration
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', 'AC1915744a1295f8c15ab863e13705d1dd')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', 'dbefb371115d778f14e2bee6f483883d')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '18333624757')

    # Admin phone numbers as a comma-separated list in environment variable
    ADMIN_PHONE_NUMBERS = os.environ.get('ADMIN_PHONE_NUMBERS', '7074954246').split(',')
