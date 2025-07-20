from flask_mail import Message
from extensions import mail  # Import 'mail' from extensions.py
from config import Config  # Import Config at the module level


def generate_admin_sub_filled_email(teacher, sub_request, substitute):
    """
    Generates standardized email content for admins when a substitute request is filled.
    """
    subject = "Substitute Position Filled"
    body = f"""A substitute position has been filled:
    👨‍🏫 Teacher: {teacher.name}
    📅 Date: {sub_request.date.strftime('%Y-%m-%d')}
    ⏰ Time: {sub_request.time}
    ✅ Filled by: {substitute.name} ({substitute.email})
    🔍 Reason: {sub_request.reason or 'Not specified'}
    📌 Details: {sub_request.details or 'No additional details provided'}
    📚 Grade: {getattr(sub_request.grade, 'name', 'Not specified')}
    📖 Subject: {getattr(sub_request.subject, 'name', 'Not specified')}"""

    return subject, body


def generate_teacher_sub_filled_email(sub_request, substitute):
    """
    Generates standardized email content for teachers when their substitute request is filled.
    """
    subject = "Your Substitute Request Has Been Filled"
    body = f"""Good news! Your substitute request has been filled:
    📅 Date: {sub_request.date.strftime('%Y-%m-%d')}
    ⏰ Time: {sub_request.time}
    🔍 Reason: {sub_request.reason or 'Not specified'}
    ✅ Filled by: {substitute.name}
    📧 Contact: {substitute.email}
    📚 Grade: {getattr(sub_request.grade, 'name', 'Not specified')}
    📖 Subject: {getattr(sub_request.subject, 'name', 'Not specified')}"""

    return subject, body


def generate_substitute_confirmation_email(teacher, sub_request):
    """
    Generates standardized email content for substitutes confirming their acceptance.
    """
    subject = "Substitute Position Confirmation"
    body = f"""Thank you for accepting the substitute position:
    👨‍🏫 Teacher: {teacher.name}
    📅 Date: {sub_request.date.strftime('%Y-%m-%d')}
    ⏰ Time: {sub_request.time}
    🔍 Reason: {sub_request.reason or 'Not specified'}
    📌 Details: {sub_request.details or 'No additional details provided'}
    📚 Grade: {getattr(sub_request.grade, 'name', 'Not specified')}
    📖 Subject: {getattr(sub_request.subject, 'name', 'Not specified')}
    ⚠️ Important: Please report to the front office at least 10 minutes before the scheduled time."""

    return subject, body


def filter_eligible_substitutes(teacher, substitutes):
    """
    Filters substitutes based on matching grades and subjects with the teacher.

    Rules:
    1. If a substitute has selected "All" for grades and "All" for subjects, they receive any request.
    2. If the grade from the teacher does not match the grade preference of the substitute, 
       the substitute does not get the request.
    3. If the substitute has specified a subject and the teacher's subject is specific and doesn't match, 
       the substitute does not get the request.

    :param teacher: The teacher object
    :param substitutes: List of substitute user objects
    :return: Filtered list of eligible substitutes
    """
    eligible_substitutes = []

    # Constants for "All" grade and subject IDs
    ALL_GRADE_ID = 9  # ID for "All" grade
    ALL_SUBJECT_ID = 8  # ID for "All" subject

    for substitute in substitutes:
        # Get the set of grade IDs and subject IDs for the substitute and teacher
        sub_grade_ids = {grade.id for grade in substitute.grades}
        sub_subject_ids = {subject.id for subject in substitute.subjects}
        teacher_grade_ids = {grade.id for grade in teacher.grades}
        teacher_subject_ids = {subject.id for subject in teacher.subjects}

        # Rule 1: If substitute selected "All" for both grades and subjects
        if ALL_GRADE_ID in sub_grade_ids and ALL_SUBJECT_ID in sub_subject_ids:
            eligible_substitutes.append(substitute)
            continue

        # Check for grade match
        grade_match = False
        # If substitute has "All" grade or there's an overlap in grades
        if ALL_GRADE_ID in sub_grade_ids or (sub_grade_ids and teacher_grade_ids and sub_grade_ids.intersection(teacher_grade_ids)):
            grade_match = True

        # Check for subject match
        subject_match = False
        # If substitute has "All" subject or there's an overlap in subjects
        if ALL_SUBJECT_ID in sub_subject_ids or (sub_subject_ids and teacher_subject_ids and sub_subject_ids.intersection(teacher_subject_ids)):
            subject_match = True

        # If both grade and subject match, add to eligible substitutes
        if grade_match and subject_match:
            eligible_substitutes.append(substitute)

    return eligible_substitutes


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
        # Use twilio_initialized from extensions.py
        from extensions import twilio_initialized, twilio_client

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
