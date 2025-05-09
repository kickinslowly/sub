from flask_mail import Message
from extensions import mail  # Import 'mail' from extensions.py, not app.py.


def send_email(subject, recipient, body):
    """
    Sends an email to the specified recipient(s).
    :param subject: Subject of the email
    :param recipient: A single email address or a list of addresses
    :param body: Body content of the email
    """
    try:
        msg = Message(subject, sender='your_email@gmail.com', recipients=[recipient])
        msg.body = body
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Failed to send email to {recipient}. Error: {e}")
        return False
