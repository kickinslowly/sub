import os

class Config:
    SECRET_KEY = 'f8ff728627036ae23e1c0b0dd02b3a69f0933da51b3493bb1d0d95cda12daff8'

    SQLALCHEMY_DATABASE_URI = 'sqlite:///portal.db'  # Use SQLite for simplicity
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    GOOGLE_CLIENT_ID = '584875541165-6b95b2d7k5vlbs7ebqmpu8md94k2q4k5.apps.googleusercontent.com'
    GOOGLE_CLIENT_SECRET = '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'
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'kickinslowly@gmail.com'
    MAIL_PASSWORD = 'suwj zxyj xiwt vozh'
    ADMIN_EMAILS = ['kickinslowly@gmail.com']

    # # Twilio configuration
    # TWILIO_ACCOUNT_SID = 'AC1915744a1295f8c15ab863e13705d1dd'
    # TWILIO_AUTH_TOKEN = 'ec81dae08e2819332fcbbc8630266d33'
    # TWILIO_PHONE_NUMBER = '18333624757'
    # ADMIN_PHONE_NUMBERS = ['7074954246']
