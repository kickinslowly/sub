from flask_mail import Message
from extensions import mail  # Import 'mail' from extensions.py
from config import Config  # Import Config at the module level
from datetime import datetime
from functools import wraps
from flask import redirect, url_for, flash, session
import re
import pytz  # For timezone handling

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


def filter_eligible_substitutes(teacher, substitutes=None):
    """
    Filters substitutes based on matching grades and subjects with the teacher.
    Uses SQLAlchemy queries to filter at the database level for better performance.

    Rules:
    1. If a substitute has selected "All" for grades and "All" for subjects, they receive any request.
    2. If the grade from the teacher does not match the grade preference of the substitute, 
       the substitute does not get the request.
    3. If the substitute has specified a subject and the teacher's subject is specific and doesn't match, 
       the substitute does not get the request.
    4. If the substitute and teacher share at least one school, they match.

    :param teacher: The teacher object
    :param substitutes: Optional parameter (kept for backward compatibility)
    :return: Filtered list of eligible substitutes
    """
    from models import User, Grade, Subject, School, user_grades, user_subjects, user_schools
    from extensions import db
    from sqlalchemy import or_, and_

    # Constants for "All" grade and subject IDs
    ALL_GRADE_ID = 9  # ID for "All" grade
    ALL_SUBJECT_ID = 8  # ID for "All" subject

    # Get teacher's grade, subject, and school IDs
    teacher_grade_ids = [grade.id for grade in teacher.grades]
    teacher_subject_ids = [subject.id for subject in teacher.subjects]
    teacher_school_ids = [school.id for school in teacher.schools]

    # Start with a base query for substitute users
    query = db.session.query(User).filter(User.role == 'substitute')

    # Create a subquery for substitutes with "All" grade AND "All" subject
    all_grade_and_subject_query = (
        db.session.query(User.id)
        .join(user_grades)
        .join(user_subjects)
        .filter(User.role == 'substitute')
        .filter(Grade.id == ALL_GRADE_ID)
        .filter(Subject.id == ALL_SUBJECT_ID)
    )

    # Create a query for grade matching (either "All" grade or matching specific grades)
    grade_match_query = (
        db.session.query(User.id)
        .join(user_grades)
        .filter(User.role == 'substitute')
        .filter(or_(
            Grade.id == ALL_GRADE_ID,
            Grade.id.in_(teacher_grade_ids) if teacher_grade_ids else False
        ))
    )

    # Create a query for subject matching (either "All" subject or matching specific subjects)
    subject_match_query = (
        db.session.query(User.id)
        .join(user_subjects)
        .filter(User.role == 'substitute')
        .filter(or_(
            Subject.id == ALL_SUBJECT_ID,
            Subject.id.in_(teacher_subject_ids) if teacher_subject_ids else False
        ))
    )

    # School matching is more complex due to the empty list rules
    if not teacher_school_ids:
        # If teacher has no schools, all substitutes match for schools
        school_match_query = db.session.query(User.id).filter(User.role == 'substitute')
    else:
        # Create a query for school matching
        # Either substitute has no schools, or there's an overlap in schools
        school_match_query = (
            db.session.query(User.id)
            .outerjoin(user_schools)
            .filter(User.role == 'substitute')
            .filter(or_(
                ~User.schools.any(),  # No schools assigned to substitute
                School.id.in_(teacher_school_ids)
            ))
        )

    # Combine the queries:
    # 1. Users with "All" grade AND "All" subject
    # 2. Users with matching grade AND matching subject AND matching school
    eligible_substitutes = (
        query.filter(or_(
            User.id.in_(all_grade_and_subject_query),
            and_(
                User.id.in_(grade_match_query),
                User.id.in_(subject_match_query),
                User.id.in_(school_match_query)
            )
        )).all()
    )

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


# Role-based access control helper functions
def is_tech_coordinator(user):
    """
    Checks if a user is a tech coordinator (admin_l1).
    
    :param user: User object to check
    :return: True if the user is a tech coordinator, False otherwise
    """
    return user.email in Config.TECH_COORDINATOR_EMAILS


def is_admin_l2(user):
    """
    Checks if a user is a level 2 admin.
    
    :param user: User object to check
    :return: True if the user is a level 2 admin, False otherwise
    """
    return user.role == 'admin_l2'


def is_admin(user):
    """
    Checks if a user is any type of admin (admin_l1 or admin_l2).
    
    :param user: User object to check
    :return: True if the user is an admin, False otherwise
    """
    return user.role in ['admin_l1', 'admin_l2']


def requires_role(role):
    """
    Decorator that checks if a user has the required role.
    
    :param role: The required role ('admin', 'admin_l1', 'admin_l2', 'teacher', 'substitute')
    :return: The decorated function if the user has the required role, otherwise redirects to index
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Import is_authenticated from app to avoid circular imports
            from app import is_authenticated
            
            if not is_authenticated(required_role=role):
                flash('Access denied. Insufficient permissions.')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def convert_utc_to_local(utc_dt, timezone_str='UTC'):
    """
    Convert a UTC datetime to a local timezone.
    
    :param utc_dt: UTC datetime object
    :param timezone_str: Timezone string (e.g., 'America/New_York')
    :return: Datetime object in the specified timezone
    """
    if not utc_dt:
        return None
    
    try:
        # Ensure the datetime is timezone-aware and in UTC
        if utc_dt.tzinfo is None:
            utc_dt = pytz.utc.localize(utc_dt)
        
        # Convert to the target timezone
        local_tz = pytz.timezone(timezone_str)
        local_dt = utc_dt.astimezone(local_tz)
        
        return local_dt
    except Exception as e:
        print(f"Error converting timezone: {e}")
        # Return the original datetime if there's an error
        return utc_dt


def format_datetime(dt, format_str='%B %d, %Y at %I:%M %p'):
    """
    Format a datetime object as a string.
    
    :param dt: Datetime object
    :param format_str: Format string for strftime
    :return: Formatted datetime string
    """
    if not dt:
        return ""
    
    try:
        return dt.strftime(format_str)
    except Exception as e:
        print(f"Error formatting datetime: {e}")
        return str(dt)


# Register Jinja2 template filters
def register_template_filters(app):
    """
    Register custom template filters for the Flask app.
    
    :param app: Flask application instance
    """
    @app.template_filter('to_local_tz')
    def to_local_tz_filter(dt, timezone_str='UTC', format_str='%B %d, %Y at %I:%M %p'):
        """
        Jinja2 filter to convert UTC datetime to local timezone and format it.
        
        Usage in template: {{ request.created_at | to_local_tz(user.timezone) }}
        
        :param dt: UTC datetime object
        :param timezone_str: Timezone string (e.g., 'America/New_York')
        :param format_str: Format string for strftime
        :return: Formatted datetime string in local timezone
        """
        local_dt = convert_utc_to_local(dt, timezone_str)
        return format_datetime(local_dt, format_str)
