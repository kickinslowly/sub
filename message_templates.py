"""
Message Templates Module

This module centralizes all message templates used in the application.
It includes functions for generating both email and SMS templates for various notifications.
"""

import logging

# Configure logger
logger = logging.getLogger(__name__)

# Email Templates

def generate_admin_sub_filled_email(teacher, sub_request, substitute):
    """
    Generates standardized email content for admins when a substitute request is filled.
    """
    subject = "Substitute Position Filled"
    body = f"""Hello,

This is a message from EZ-Sub, the teacher-substitute notification system.

A substitute position has been filled:
👨‍🏫 Teacher: {teacher.name}
📅 Date: {sub_request.date.strftime('%B %d, %Y')}
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
    body = f"""Hello,

This is a message from EZ-Sub, the teacher-substitute notification system.

Good news! Your substitute request has been filled:
📅 Date: {sub_request.date.strftime('%B %d, %Y')}
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
    body = f"""Hello,

This is a message from EZ-Sub, the teacher-substitute notification system.

Thank you for accepting the substitute position:
👨‍🏫 Teacher: {teacher.name}
📅 Date: {sub_request.date.strftime('%B %d, %Y')}
⏰ Time: {sub_request.time}
🔍 Reason: {sub_request.reason or 'Not specified'}
📌 Details: {sub_request.details or 'No additional details provided'}
📚 Grade: {getattr(sub_request.grade, 'name', 'Not specified')}
📖 Subject: {getattr(sub_request.subject, 'name', 'Not specified')}
⚠️ Important: Please report to the front office at least 10 minutes before the scheduled time."""

    return subject, body


def generate_substitute_notification_email(teacher, date, time, grade_name, subject_name, details, request_link):
    """
    Generates standardized email content for notifying substitutes about new requests.
    """
    subject = "New Substitute Request Available"
    body = f"""Hello,

This is a message from EZ-Sub, the teacher-substitute notification system.

A new substitute request has been posted:
📅 Date: {date}
⏰ Time: {time}
👨‍🏫 Teacher: {teacher.name}
📚 Grade: {grade_name}
📖 Subject: {subject_name}
📌 Details: {details or 'No additional details provided'}
👉 Accept the request here: {request_link}"""

    return subject, body


def generate_admin_notification_email(teacher, date, time, grade_name, subject_name, details, reason=None):
    """
    Generates standardized email content for notifying admins about new requests.
    """
    subject = "New Substitute Request Created"
    body = f"""Hello,

This is a message from EZ-Sub, the teacher-substitute notification system.

A new substitute request has been created:
👨‍🏫 Teacher: {teacher.name}
📅 Date: {date}
⏰ Time: {time}
📚 Grade: {grade_name}
📖 Subject: {subject_name}
🔍 Reason: {reason or 'Not specified'}
📌 Details: {details or 'No additional details provided'}"""

    return subject, body


def generate_teacher_confirmation_email(date, time, grade_name, subject_name, details, reason=None):
    """
    Generates standardized email content for confirming request creation to teachers.
    """
    subject = "Your Substitute Request Has Been Created"
    body = f"""Hello,

This is a message from EZ-Sub, the teacher-substitute notification system.

A substitute request has been created:
📅 Date: {date}
⏰ Time: {time}
📚 Grade: {grade_name}
📖 Subject: {subject_name}
🔍 Reason: {reason or 'Not specified'}
📌 Details: {details or 'No additional details provided'}
You will be notified when a substitute accepts this request."""

    return subject, body


# SMS Templates

def generate_substitute_notification_sms(teacher, date, time, grade_name, subject_name, request_link):
    """
    Generates SMS content for notifying substitutes about new requests.
    """
    return f"[EZ-Sub] New sub request: Teacher {teacher.name}, Date {date}, Time {time}, Grade {grade_name}, Subject {subject_name}. Accept at: {request_link}"


def generate_admin_notification_sms(teacher, date, time, grade_name, subject_name, reason):
    """
    Generates SMS content for notifying admins about new requests.
    """
    return f"[EZ-Sub] New sub request: Teacher {teacher.name}, Date {date}, Time {time}, Grade {grade_name}, Subject {subject_name}, Reason {reason or 'Not specified'}"


def generate_teacher_confirmation_sms(date, time):
    """
    Generates SMS content for confirming request creation to teachers.
    """
    return f"[EZ-Sub] Sub Request created for {date}, {time}. You will be notified when a substitute accepts."


def generate_admin_sub_filled_sms(teacher, sub_request, substitute_name):
    """
    Generates SMS content for notifying admins when a substitute position is filled.
    """
    return f"[EZ-Sub] Sub position filled: {teacher.name}, {sub_request.date.strftime('%B %d, %Y')}, {sub_request.time}, filled by {substitute_name}"