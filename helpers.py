from flask_mail import Message
from extensions import mail  # Import 'mail' from extensions.py
from config import Config  # Import Config at the module level
from datetime import datetime
import re

def calculate_hours_from_time_range(time_range):
    """
    Calculate the number of hours from a time range string in the format "HH:MM AM/PM - HH:MM AM/PM"
    
    :param time_range: String in the format "HH:MM AM/PM - HH:MM AM/PM"
    :return: Float representing the number of hours
    """
    if not time_range or not isinstance(time_range, str):
        return 0.0
    
    # Split the time range into start and end times
    try:
        start_time_str, end_time_str = time_range.split(' - ')
    except ValueError:
        # If the time range is not in the expected format, return 0
        return 0.0
    
    # Parse the start and end times
    try:
        start_time = datetime.strptime(start_time_str, '%I:%M %p')
        end_time = datetime.strptime(end_time_str, '%I:%M %p')
        
        # Calculate the time difference in hours
        # Since we're only interested in the time part, we need to handle cases where end_time is earlier than start_time
        # (which would happen if the times are on the same day)
        hours_diff = (end_time.hour - start_time.hour) + (end_time.minute - start_time.minute) / 60.0
        
        # If the result is negative, it means the end time is on the next day (e.g., overnight shift)
        # In this case, add 24 hours
        if hours_diff < 0:
            hours_diff += 24.0
            
        return round(hours_diff, 2)
    except ValueError:
        # If the time strings are not in the expected format, return 0
        return 0.0

def calculate_total_hours_out(requests):
    """
    Calculate the total hours out from a list of substitute requests
    
    :param requests: List of SubstituteRequest objects
    :return: Float representing the total hours
    """
    total_hours = 0.0
    
    for request in requests:
        hours = calculate_hours_from_time_range(request.time)
        total_hours += hours
    
    return round(total_hours, 2)


def generate_admin_sub_filled_email(teacher, sub_request, substitute):
    """
    Generates standardized email content for admins when a substitute request is filled.
    """
    subject = "Substitute Position Filled"
    body = f"""A substitute position has been filled:
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
    body = f"""Good news! Your substitute request has been filled:
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
    body = f"""Thank you for accepting the substitute position:
    👨‍🏫 Teacher: {teacher.name}
    📅 Date: {sub_request.date.strftime('%B %d, %Y')}
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

        # Check for school match
        school_match = False
        # If substitute doesn't have a school_id assigned, show all schools
        if substitute.school_id is None:
            school_match = True
        # If teacher doesn't have a school_id assigned, show to all substitutes
        elif teacher.school_id is None:
            school_match = True
        # If teacher has a school_id and it matches the substitute's school_id
        elif teacher.school_id == substitute.school_id:
            school_match = True
            
        # If grade, subject, and school match, add to eligible substitutes
        if grade_match and subject_match and school_match:
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


def is_future_date_time(date_str, time_range):
    """
    Validates if a date and time are in the future.
    
    :param date_str: Date string in 'MM/DD/YYYY' format
    :param time_range: Time range string in 'HH:MM AM/PM - HH:MM AM/PM' format
    :return: True if the date and time are in the future, False otherwise
    """
    try:
        # Parse the date string
        request_date = datetime.strptime(date_str, '%m/%d/%Y').date()
        
        # Get the current date
        current_date = datetime.now().date()
        
        # If the date is in the past, return False
        if request_date < current_date:
            return False
        
        # If the date is in the future, return True
        if request_date > current_date:
            return True
        
        # If the date is today, check the time
        # Extract the start time from the time range
        start_time_str = time_range.split(' - ')[0]
        
        # Parse the start time
        start_time = datetime.strptime(start_time_str, '%I:%M %p')
        
        # Create a datetime object for the request date and time
        request_datetime = datetime.combine(
            request_date,
            start_time.time()
        )
        
        # Get the current datetime
        current_datetime = datetime.now()
        
        # Return True if the request datetime is in the future
        return request_datetime > current_datetime
    
    except (ValueError, IndexError) as e:
        # If there's an error parsing the date or time, log it and return False
        print(f"Error validating date/time: {e}")
        return False
