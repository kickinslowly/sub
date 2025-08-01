from flask_mail import Message
from extensions import mail  # Import 'mail' from extensions.py
from config import Config  # Import Config at the module level
from datetime import datetime
from functools import wraps
from flask import redirect, url_for, flash, session
import re
import pytz  # For timezone handling
import logging

logger = logging.getLogger(__name__)

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
    Only includes filled requests (status != "Open")
    
    :param requests: List of SubstituteRequest objects
    :return: Float representing the total hours
    """
    total_hours = 0.0
    
    for request in requests:
        # Only include filled requests (status != "Open")
        if request.status != "Open":
            hours = calculate_hours_from_time_range(request.time)
            total_hours += hours
    
    return round(total_hours, 2)


# Import email templates from message_templates.py
from message_templates import (
    generate_admin_sub_filled_email,
    generate_teacher_sub_filled_email,
    generate_substitute_confirmation_email
)


def is_substitute_available(substitute, date, time_range=None):
    """
    Checks if a substitute is available for a specific date and time.
    Uses TimeRange objects for proper time range comparison, including overnight ranges.
    
    :param substitute: The substitute user object
    :param date: The date to check (datetime.date object)
    :param time_range: Optional time range to check (e.g., "08:00-12:00" or "08:00 AM - 12:00 PM")
    :return: True if available, False if unavailable
    """
    from models import SubstituteUnavailability
    from datetime import datetime, timedelta
    from time_utils import TimeRange, parse_time_range
    
    # If no time range is specified, we're only checking for all-day unavailability
    if time_range:
        # Parse the requested time range into a TimeRange object
        try:
            request_time_range = parse_time_range(time_range)
        except ValueError as e:
            logger.error(f"Error parsing time range '{time_range}': {e}")
            # If we can't parse the time range, assume the substitute is unavailable
            return False
    
    # Check for direct date match
    unavailability = SubstituteUnavailability.query.filter_by(
        user_id=substitute.id,
        date=date
    ).all()
    
    # If there's an all-day unavailability for this date, the substitute is unavailable
    for item in unavailability:
        if item.all_day:
            return False
        
        # If checking a specific time range and there's an overlap, the substitute is unavailable
        if time_range and item.time_range:
            try:
                # Parse the unavailability time range
                item_time_range = parse_time_range(item.time_range)
                
                # Check for overlap
                if request_time_range.overlaps(item_time_range):
                    return False
            except ValueError as e:
                logger.error(f"Error parsing unavailability time range '{item.time_range}': {e}")
                # If we can't parse the time range, assume there's an overlap to be safe
                return False
    
    # Check for repeating unavailability
    # Get the day of week name for the requested date
    day_of_week = date.strftime("%A")  # Returns Monday, Tuesday, etc.
    
    # Find any repeating unavailability for this day of week
    repeating_unavailability = SubstituteUnavailability.query.filter(
        SubstituteUnavailability.user_id == substitute.id,
        SubstituteUnavailability.repeat_pattern == day_of_week,
        (SubstituteUnavailability.repeat_until >= date) | (SubstituteUnavailability.repeat_until == None),
        SubstituteUnavailability.date <= date  # Only consider patterns that start on or before the requested date
    ).all()
    
    # If there's a repeating all-day unavailability for this day of week, the substitute is unavailable
    for item in repeating_unavailability:
        if item.all_day:
            return False
        
        # If checking a specific time range and there's an overlap, the substitute is unavailable
        if time_range and item.time_range:
            try:
                # Parse the unavailability time range
                item_time_range = parse_time_range(item.time_range)
                
                # Check for overlap
                if request_time_range.overlaps(item_time_range):
                    return False
            except ValueError as e:
                logger.error(f"Error parsing repeating unavailability time range '{item.time_range}': {e}")
                # If we can't parse the time range, assume there's an overlap to be safe
                return False
    
    # If we get here, the substitute is available
    return True


def filter_eligible_substitutes(teacher, request_date=None, request_time=None, school_id=None, substitutes=None):
    """
    Filters substitutes based on matching grades and subjects with the teacher.
    Uses SQLAlchemy queries to filter at the database level for better performance.

    Rules:
    1. If a substitute has selected "All" for grades and "All" for subjects, they receive any request.
    2. If the grade from the teacher does not match the grade preference of the substitute, 
       the substitute does not get the request.
    3. If the substitute has specified a subject and the teacher's subject is specific and doesn't match, 
       the substitute does not get the request.
    4. If a specific school_id is provided, only substitutes associated with that school will match.
    5. If a substitute has marked themselves as unavailable for the date/time, they are excluded.

    :param teacher: The teacher object
    :param request_date: The date of the request (datetime.date object)
    :param request_time: The time range of the request (e.g., "08:00-12:00")
    :param school_id: The specific school ID for the substitute request
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

    # Start with a base query for substitute users
    query = db.session.query(User).filter(User.role == 'substitute')

    # Create a subquery for substitutes with "All" grade AND "All" subject
    all_grade_and_subject_query = (
        db.session.query(User.id)
        .join(user_grades)
        .join(Grade, user_grades.c.grade_id == Grade.id)
        .join(user_subjects)
        .join(Subject, user_subjects.c.subject_id == Subject.id)
        .filter(User.role == 'substitute')
        .filter(Grade.id == ALL_GRADE_ID)
        .filter(Subject.id == ALL_SUBJECT_ID)
    )

    # Create a query for grade matching (either "All" grade or matching specific grades)
    grade_match_query = (
        db.session.query(User.id)
        .join(user_grades)
        .join(Grade, user_grades.c.grade_id == Grade.id)
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
        .join(Subject, user_subjects.c.subject_id == Subject.id)
        .filter(User.role == 'substitute')
        .filter(or_(
            Subject.id == ALL_SUBJECT_ID,
            Subject.id.in_(teacher_subject_ids) if teacher_subject_ids else False
        ))
    )

    # School matching based on the specific school_id
    if school_id:
        # Only match substitutes associated with the specific school
        school_match_query = (
            db.session.query(User.id)
            .join(user_schools)
            .join(School)
            .filter(User.role == 'substitute')
            .filter(School.id == school_id)
        )
    else:
        # If no school_id is provided, match all substitutes (backward compatibility)
        school_match_query = db.session.query(User.id).filter(User.role == 'substitute')

    # Combine the queries:
    # 1. Users with "All" grade AND "All" subject AND matching school
    # 2. Users with matching grade AND matching subject AND matching school
    eligible_substitutes = (
        query.filter(or_(
            and_(
                User.id.in_(all_grade_and_subject_query),
                User.id.in_(school_match_query)
            ),
            and_(
                User.id.in_(grade_match_query),
                User.id.in_(subject_match_query),
                User.id.in_(school_match_query)
            )
        )).all()
    )
    
    # If date and time are provided, filter out unavailable substitutes
    if request_date:
        # Filter out substitutes who are unavailable for this date/time
        available_substitutes = []
        for substitute in eligible_substitutes:
            if is_substitute_available(substitute, request_date, request_time):
                available_substitutes.append(substitute)
        return available_substitutes
    
    return eligible_substitutes


def send_email(subject, recipient, body):
    """
    Sends an email to the specified recipient(s).
    :param subject: Subject of the email
    :param recipient: A single email address or a list of addresses
    :param body: Body content of the email
    :return: True if successful, False otherwise
    """
    # Validate recipient is not empty
    if not recipient or not isinstance(recipient, str) or not recipient.strip():
        logger.warning("Attempted to send email with empty recipient")
        return False
    
    # Validate mail configuration
    if not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD:
        logger.error("Mail configuration is incomplete. MAIL_USERNAME and MAIL_PASSWORD must be set.")
        return False
        
    try:
        # Create the message object
        msg = Message(subject, sender=Config.MAIL_USERNAME, recipients=[recipient])
        msg.body = body
        
        # Import the mail object here to avoid circular imports
        from extensions import mail
        
        # Import the Flask app to create an application context
        # This is needed when sending emails from background threads
        from app import app
        
        # Create an application context before sending the email
        with app.app_context():
            # Send the email
            mail.send(msg)
            # Log successful email sending
            logger.info(f"Email sent to {recipient}, Subject: {subject}")
        return True
    except ImportError as e:
        logger.error(f"Failed to import required modules for email sending: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to send email to {recipient}. Error: {e}")
        # Log more detailed error information for debugging
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


# Import SMS templates from message_templates.py
from message_templates import (
    generate_substitute_notification_sms,
    generate_admin_notification_sms,
    generate_teacher_confirmation_sms,
    generate_admin_sub_filled_sms
)


def send_sms(to_number, body):
    """
    Sends an SMS message to the specified phone number.
    :param to_number: The recipient's phone number
    :param body: The message content
    :return: True if successful, False otherwise
    """
    # Check if the phone number is valid
    if not to_number or not isinstance(to_number, str) or not to_number.strip():
        logger.warning("Invalid phone number provided")
        return False

    try:
        # Import Twilio configuration here to avoid issues with Flask context
        from extensions import twilio_initialized, twilio_client
        from config import Config

        # Check if Twilio is properly initialized
        if not twilio_initialized:
            logger.warning("Twilio is not properly initialized. SMS will not be sent.")
            # Log the message that would have been sent for debugging
            logger.info(f"SMS would have been sent to {to_number}: {body}")
            return False

        if twilio_client is None:
            logger.warning("Twilio client not initialized")
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
        logger.info(f"SMS sent to {formatted_number}, SID: {message.sid}")
        return True
    except ImportError:
        logger.error("Could not import twilio_enabled flag. SMS will not be sent.")
        return False
    except Exception as e:
        logger.error(f"Failed to send SMS to {to_number}. Error: {e}")
        return False


def is_future_date_time(date_str, time_range, user=None):
    """
    Validates if a date and time are in the future and not on a weekend, using the user's timezone if provided.
    
    :param date_str: Date string in 'MM/DD/YYYY' format
    :param time_range: Time range string in 'HH:MM AM/PM - HH:MM AM/PM' format
    :param user: User object with timezone information (optional)
    :return: True if the date and time are in the future and not on a weekend, False otherwise
    """
    try:
        from time_utils import get_current_time_in_timezone, localize_datetime
        
        # Parse the date string
        request_date = datetime.strptime(date_str, '%m/%d/%Y').date()
        
        # Check if the date is a weekend (Saturday=5, Sunday=6)
        if request_date.weekday() >= 5:
            logger.info(f"Date {date_str} is a weekend (weekday={request_date.weekday()}). Weekend requests are not allowed.")
            return False
        
        # Get the user's timezone or default to UTC
        timezone_str = user.timezone if user and hasattr(user, 'timezone') else 'UTC'
        
        # Get the current datetime in the user's timezone
        current_datetime = get_current_time_in_timezone(timezone_str)
        current_date = current_datetime.date()
        
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
        
        # Localize the request datetime to the user's timezone
        request_datetime = localize_datetime(request_datetime, timezone_str)
        
        # Return True if the request datetime is in the future
        return request_datetime > current_datetime
    
    except (ValueError, IndexError) as e:
        # If there's an error parsing the date or time, log it and return False
        logger.error(f"Error validating date/time: {e}")
        return False


# Role-based access control helper functions
def is_tech_coordinator(user):
    """
    Checks if a user is a tech coordinator (admin_l1).
    
    :param user: User object to check
    :return: True if the user is a tech coordinator, False otherwise
    """
    # Check if the user has the admin_l1 role or if their email is in the tech coordinator list
    return user.role == 'admin_l1' or user.email in Config.TECH_COORDINATOR_EMAILS






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
    
    # If timezone_str is None, use UTC as default
    if timezone_str is None:
        timezone_str = 'UTC'
    
    try:
        # Ensure the datetime is timezone-aware and in UTC
        if utc_dt.tzinfo is None:
            utc_dt = pytz.utc.localize(utc_dt)
        
        # Convert to the target timezone
        local_tz = pytz.timezone(timezone_str)
        local_dt = utc_dt.astimezone(local_tz)
        
        return local_dt
    except Exception as e:
        logger.error(f"Error converting timezone: {timezone_str}")
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
        logger.error(f"Error formatting datetime: {e}")
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
