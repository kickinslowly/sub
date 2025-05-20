from flask_mail import Message
from extensions import mail, twilio_client  # Import 'mail' and 'twilio_client' from extensions.py
from config import Config  # Import Config at the module level


def send_email(subject, recipient, body):
    """
    Sends an email to the specified recipient(s).
    :param subject: Subject of the email
    :param recipient: A single email address or a list of addresses
    :param body: Body content of the email
    """
    try:
        msg = Message(subject, sender=Config.MAIL_USERNAME, recipients=[recipient])
        msg.body = body
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Failed to send email to {recipient}. Error: {e}")
        return False


def send_sms(to_number, body):
    """
    Sends an SMS message to the specified phone number.
    :param to_number: The recipient's phone number
    :param body: The message content
    :return: True if successful, False otherwise
    """
    # Check if the phone number is valid
    if not to_number or not isinstance(to_number, str) or not to_number.strip():
        print("Invalid phone number provided")
        return False

    try:
        # Import here to avoid circular imports
        from app import twilio_initialized

        # Check if Twilio is properly initialized
        if not twilio_initialized:
            print("Twilio is not properly initialized. SMS will not be sent.")
            return False

        if twilio_client is None:
            print("Twilio client not initialized")
            return False

        # Format the phone number if it doesn't start with +
        formatted_number = to_number
        if not to_number.startswith('+'):
            formatted_number = '+1' + to_number  # Assuming US numbers

        message = twilio_client.messages.create(
            body=body,
            from_=Config.TWILIO_PHONE_NUMBER,
            to=formatted_number
        )
        print(f"SMS sent to {formatted_number}, SID: {message.sid}")
        return True
    except ImportError:
        print("Could not import twilio_initialized flag. SMS will not be sent.")
        return False
    except Exception as e:
        print(f"Failed to send SMS to {to_number}. Error: {e}")
        return False
