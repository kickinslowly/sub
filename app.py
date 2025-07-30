from flask import Flask, redirect, url_for, session, render_template, request, flash, jsonify
from authlib.integrations.flask_client import OAuth
from config import Config
from datetime import datetime, timedelta
from models import User, SubstituteRequest, SubstituteUnavailability, Grade, Subject, School, Organization, user_grades, user_subjects, user_schools # Import models
from sqlalchemy.orm import aliased
import uuid
import sqlite3
import os
import sqlalchemy.exc  # Import SQLAlchemy exceptions
from werkzeug.security import check_password_hash
from twilio.rest import Client
from helpers import requires_role, is_tech_coordinator, register_template_filters
import logging
from logging_config import configure_logging
# Import message templates
from message_templates import (
    generate_substitute_notification_email,
    generate_admin_notification_email,
    generate_teacher_confirmation_email,
    generate_substitute_notification_sms,
    generate_admin_notification_sms,
    generate_teacher_confirmation_sms,
    generate_admin_sub_filled_email,
    generate_teacher_sub_filled_email,
    generate_substitute_confirmation_email,
    generate_admin_sub_filled_sms,
    generate_substitute_confirmation_sms
)

# Initialize Flask app
app = Flask(__name__)
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config.from_object(Config)

# Configure logging
logger = configure_logging(app)

# Validate configuration
try:
    Config.validate_config()
except EnvironmentError as e:
    app.logger.error(f"Configuration error: {e}")
    # Continue with initialization, but some features may be disabled

# Initialize extensions
from extensions import db, mail, csrf, limiter
db.init_app(app)
mail.init_app(app)
csrf.init_app(app)
limiter.init_app(app)

# Register blueprints
from blueprints.admin import admin_bp
from blueprints.api import api_bp
from blueprints.auth import auth_bp
from blueprints.requests import requests_bp
from blueprints.substitutes import substitutes_bp
from blueprints.users import users_bp
from blueprints.super_admin import super_admin_bp

app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(requests_bp)
app.register_blueprint(substitutes_bp)
app.register_blueprint(users_bp)
app.register_blueprint(super_admin_bp)

# Configure default rate limits
limiter.default_limits = ["200 per day", "50 per hour"]

# Register custom template filters
register_template_filters(app)

# Initialize database migrations
from migrations import init_migrations
init_migrations(app)
oauth = OAuth(app)


# Initialize Twilio client
if all([Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN, Config.TWILIO_PHONE_NUMBER]):
    # Use the init_twilio function from extensions.py
    from extensions import init_twilio
    if init_twilio(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN):
        logger.info("Twilio client initialized successfully")
    else:
        logger.warning("Failed to initialize Twilio client. SMS functionality will be disabled")
else:
    logger.warning("Twilio credentials are not properly configured. SMS functionality will be disabled.")

# Import helper functions after Twilio client is initialized
from helpers import send_email, send_sms

logger.debug("Registering models...")
# Wrap database queries in app.app_context() to ensure they work
with app.app_context():
    # Tables are created by Alembic migrations, not manually
    logger.debug(f"Registered tables in metadata: {db.metadata.tables.keys()}")
    try:
        logger.debug(f"Grades: {Grade.query.all()}")
    except Exception as e:
        logger.error(f"Error querying Grades table: {e}")
        logger.info("Run 'flask db upgrade' to ensure all migrations are applied")

def seed_database():
    """
    Seed the database with initial values for grades and subjects
    if they don't already exist.
    """
    try:
        logger.info("Starting database seeding...")
        
        # Seed grades
        grades = [
            {'id': 1, 'name': 'K'},
            {'id': 2, 'name': '1'},
            {'id': 3, 'name': '2'},
            {'id': 4, 'name': '3'},
            {'id': 5, 'name': '4'},
            {'id': 6, 'name': '5'},
            {'id': 7, 'name': 'Mid'},
            {'id': 8, 'name': 'High'},
            {'id': 9, 'name': 'All'},
        ]

        for grade in grades:
            # Check if the grade already exists before inserting
            if not Grade.query.filter_by(id=grade['id']).first():
                db.session.add(Grade(id=grade['id'], name=grade['name']))
                logger.debug(f"Added grade: {grade['name']}")

        # Seed subjects
        subjects = [
            {'id': 1, 'name': 'Math'},
            {'id': 2, 'name': 'Science'},
            {'id': 3, 'name': 'English'},
            {'id': 4, 'name': 'History'},
            {'id': 5, 'name': 'PE'},
            {'id': 6, 'name': 'Art'},
            {'id': 7, 'name': 'Music'},
            {'id': 8, 'name': 'All'},
        ]

        for subject in subjects:
            # Check if the subject already exists before inserting
            if not Subject.query.filter_by(id=subject['id']).first():
                db.session.add(Subject(id=subject['id'], name=subject['name']))
                logger.debug(f"Added subject: {subject['name']}")

        # Commit changes only if we have added new data
        db.session.commit()
        logger.info("Database seeding completed successfully")
        
    except sqlalchemy.exc.ProgrammingError as e:
        logger.warning(f"Tables not ready for seeding: {e}")
        db.session.rollback()
        # We'll retry later when tables are created
    except sqlalchemy.exc.SQLAlchemyError as e:
        logger.error(f"Database error during seeding: {e}")
        db.session.rollback()
    except Exception as e:
        logger.error(f"Unexpected error during database seeding: {e}")
        db.session.rollback()


# Note: Manual schema updates have been removed.
# All schema changes are now handled through Alembic migrations.
# To create a new migration: flask db migrate -m "Description of changes"
# To apply migrations: flask db upgrade

# Database initialization has been moved to the after_request handler
# This ensures that migrations are applied before we try to seed the database
# See the initialize_database_after_first_request() function below


# Add after_request handler to initialize database after the first request
# This replaces the deprecated before_first_request decorator which was removed in Flask 2.3+
@app.after_request
def initialize_database_after_first_request(response):
    """
    Initialize the database after the first request.
    This ensures that all migrations have been applied before we try to seed the database.
    The function only runs once per application lifecycle.
    """
    if not getattr(app, '_database_initialized', False):
        logger.info("Initializing database after first request...")
        with app.app_context():
            try:
                # Seed the database with initial data
                seed_database()
                
                # Check if super_admin exists, if not create one
                logger.debug("Checking for super_admin user...")
                super_admin = User.query.filter_by(role='super_admin').first()
                if not super_admin:
                    logger.info("No super_admin found. Creating super_admin user: Aaron Allen")
                    # Get the default organization
                    default_org = Organization.query.filter_by(name="Point Arena Schools").first()
                    
                    # Create super_admin user
                    super_admin = User(
                        name="Aaron Allen",
                        email="kickinslowly@gmail.com",
                        role="super_admin",
                        organization_id=default_org.id if default_org else None
                    )
                    
                    db.session.add(super_admin)
                    db.session.commit()
                    logger.info("Super admin user created successfully")
            except Exception as e:
                logger.error(f"Error initializing database: {e}")
                # Don't raise the exception - we want the application to continue running
            
            # Mark as initialized so we don't run this again
            app._database_initialized = True
    
    return response

# Google OAuth setup
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    api_base_url='https://www.googleapis.com/oauth2/v1/',  # Correct base URL
    client_kwargs={
        'scope': 'openid email profile',
    },
)


# Helper functions
def get_logged_in_user():
    """Helper function to retrieve the logged-in user from the session."""
    if 'user_info' not in session:
        return None
    
    try:
        return User.query.filter_by(email=session['user_info']['email']).first()
    except sqlalchemy.exc.OperationalError as e:
        # Handle database operational errors (like missing columns)
        logger.error(f"Database operational error in get_logged_in_user: {e}")
        flash("A database error occurred. Please contact the administrator.")
        return None
    except sqlalchemy.exc.SQLAlchemyError as e:
        # Handle other SQLAlchemy errors
        logger.error(f"Database error in get_logged_in_user: {e}")
        flash("A database error occurred. Please contact the administrator.")
        return None
    except Exception as e:
        # Handle any other unexpected errors
        logger.error(f"Unexpected error in get_logged_in_user: {e}")
        flash("An unexpected error occurred. Please contact the administrator.")
        return None


def filter_by_organization(query, model=None):
    """
    Filter a query by the current user's organization.
    
    Args:
        query: The SQLAlchemy query to filter
        model: Optional model class to use for the filter (if not provided, it's inferred from the query)
        
    Returns:
        The filtered query
    """
    user = get_logged_in_user()
    if not user or not user.organization_id:
        return query  # Return unfiltered query if no user or organization
    
    # If model is not provided, try to infer it from the query
    if not model:
        # This assumes the query is for a single model
        # For more complex queries with joins, the model should be provided
        model = query.column_descriptions[0]['entity']
    
    # Add organization filter if the model has organization_id
    if hasattr(model, 'organization_id'):
        return query.filter(model.organization_id == user.organization_id)
    
    return query  # Return unfiltered query if model doesn't have organization_id


def is_authenticated(required_role=None):
    """Checks if a user is logged in and matches the required role if specified."""
    user_info = session.get('user_info')
    if not user_info:
        return False
        
    # If no specific role is required, any authenticated user is allowed
    if not required_role:
        return True
        
    user_role = user_info.get('role')
    
    # Super admin has access to everything
    if user_role == 'super_admin':
        return True
    
    # Handle admin hierarchy
    if required_role == 'admin':
        # Both admin levels can access admin features
        return user_role in ['admin_l1', 'admin_l2']
    elif required_role == 'admin_l1':
        # Only level 1 admins (tech coordinators) can access
        return user_role == 'admin_l1'
    elif required_role == 'admin_l2':
        # Only level 2 admins can access
        return user_role == 'admin_l2'
    elif required_role == 'super_admin':
        # Only super admins can access super admin features
        return user_role == 'super_admin'
    else:
        # For other roles, exact match is required
        return user_role == required_role


# Routes
@app.route('/')
def index():
    return render_template('login.html')

@app.route('/health')
def health_check():
    return 'OK', 200

@app.route('/signup', methods=['POST'])
@limiter.limit("5 per minute")
def signup():
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            password = request.form.get('password')
            role = request.form.get('role')
            
            # Validate inputs
            if not email or not password or not role:
                flash('All fields are required')
                return redirect(url_for('index'))
            
            # Check if user already exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('An account with this email already exists')
                return redirect(url_for('index'))
            
            # Get the default organization
            default_org = Organization.query.filter_by(name="Point Arena Schools").first()
            
            # Create new user
            new_user = User(
                email=email,
                name=email.split('@')[0],  # Use part of email as name initially
                role=role,
                organization_id=default_org.id if default_org else None
            )
            
            # Set password (assuming you have a set_password method in your User model)
            # If not, you'll need to implement password hashing
            if hasattr(new_user, 'set_password'):
                new_user.set_password(password)
            else:
                # Fallback if set_password doesn't exist
                from werkzeug.security import generate_password_hash
                new_user.password_hash = generate_password_hash(password)
            
            db.session.add(new_user)
            db.session.commit()
            
            # Log the user in
            session['user_info'] = {'email': new_user.email, 'role': new_user.role}
            
            # Redirect to appropriate dashboard
            if new_user.role in ['admin_l1', 'admin_l2']:
                return redirect(url_for('admin_dashboard'))
            elif new_user.role == 'substitute':
                return redirect(url_for('substitute_dashboard'))
            else:
                return redirect(url_for('dashboard'))
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error during signup: {e}")
            flash('An error occurred during signup. Please try again.')
            return redirect(url_for('index'))
    
    return redirect(url_for('index'))


@app.route('/login')
@limiter.limit("5 per minute")
def login():
    redirect_uri = url_for('authorized', _external=True)
    return google.authorize_redirect(redirect_uri)




@app.route('/logout')
def logout():
    session.clear()
    flash('You have successfully logged out.')
    return redirect(url_for('index'))


@app.route('/login/authorized')
@limiter.limit("5 per minute")
def authorized():
    try:
        token = google.authorize_access_token()
        user_info = google.get('userinfo').json()

        try:
            # Look for existing user in the database
            user = User.query.filter_by(email=user_info['email']).first()

            # Determine user role
            # Check if the email is in TECH_COORDINATOR_EMAILS (highest level admin)
            if user_info['email'] in app.config.get('TECH_COORDINATOR_EMAILS', []):
                role = 'admin_l1'  # Level 1 admin (tech coordinator)
            # Check if the email is in ADMIN_EMAILS (level 2 admins)
            elif user_info['email'] in app.config.get('ADMIN_EMAILS', []):
                role = 'admin_l2'  # Level 2 admin (front office, principal)
            # Check if the email contains 'substitute' or 'sub' to identify substitute teachers
            elif 'substitute' in user_info['email'].lower() or 'sub' in user_info['email'].lower():
                role = 'substitute'
            else:
                role = 'teacher'

            # Get the default organization (Point Arena Schools)
            default_org = Organization.query.filter_by(name="Point Arena Schools").first()
            
            # If user doesn't exist, deny login
            if not user:
                flash('Your account does not exist. Please contact an administrator to create an account for you.')
                logger.info(f"Login denied for non-existent user: {user_info['email']}")
                return redirect(url_for('index', login_error=1))
                
            # Ensure existing user has an organization
            if user.organization_id is None and default_org:
                user.organization_id = default_org.id
            
            # Update role if it's missing or if it's the old 'admin' role that needs to be migrated
            if not user.role or (user.role == 'admin' and role in ['admin_l1', 'admin_l2']):
                user.role = role
                logger.debug(f"Updated user role from 'admin' to '{role}'")

            db.session.commit()
        except sqlalchemy.exc.OperationalError as e:
            # Handle database operational errors (like missing columns)
            logger.error(f"Database operational error during user creation/update: {e}")
            flash("A database error occurred during login. Please contact the administrator.")
            db.session.rollback()
            return redirect(url_for('index'))
        except sqlalchemy.exc.SQLAlchemyError as e:
            # Handle other SQLAlchemy errors
            logger.error(f"Database error during user creation/update: {e}")
            flash("A database error occurred during login. Please contact the administrator.")
            db.session.rollback()
            return redirect(url_for('index'))

        # Store user information in the session
        session['user_info'] = {'email': user.email, 'role': user.role}

        logger.debug(f"Role Assigned: {user.role}, Email: {user.email}")

        # Redirect to the correct dashboard based on role
        if user.role == 'super_admin':
            return redirect(url_for('super_admin.dashboard'))
        elif user.role in ['admin_l1', 'admin_l2']:
            return redirect(url_for('admin_dashboard'))
        elif user.role == 'substitute':
            return redirect(url_for('substitute_dashboard'))
        else:
            return redirect(url_for('dashboard'))

    except ValueError as e:
        flash('Invalid response from authentication server')
        logger.error(f"OAuth value error: {e}")
        return redirect(url_for('index'))
    except KeyError as e:
        flash('Missing information in authentication response')
        logger.error(f"Missing key in OAuth response: {e}")
        return redirect(url_for('index'))
    except sqlalchemy.exc.SQLAlchemyError as e:
        flash('Database error during login')
        logger.error(f"Database error: {e}")
        return redirect(url_for('index'))
    except Exception as e:
        flash('Error during login')
        logger.error(f"Login failed: {e}, User Info: {session.get('user_info', {})}")
        return redirect(url_for('index'))


@app.route('/substitute_dashboard')
def substitute_dashboard():
    if 'user_info' not in session or session['user_info']['role'] != 'substitute':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    logged_in_user = get_logged_in_user()

    # Check if logged_in_user is None
    if logged_in_user is None:
        flash("User not found. Please log in again.", "danger")
        return redirect(url_for('login'))

    # Fetch all requests in a single query and then filter in Python
    # This reduces the number of database queries
    all_requests = db.session.query(
        SubstituteRequest, User.name.label("teacher_name"), User
    ).join(User, SubstituteRequest.teacher_id == User.id).filter(
        db.or_(
            SubstituteRequest.substitute_id == logged_in_user.id,
            SubstituteRequest.status == "Open"
        )
    ).order_by(SubstituteRequest.date.asc()).all()

    # Split the results into accepted and open requests
    accepted_requests = [(req, teacher_name) for req, teacher_name, _ in all_requests 
                         if req.substitute_id == logged_in_user.id]

    # Filter open requests
    all_open_requests = [(req, teacher_name, teacher) for req, teacher_name, teacher in all_requests 
                         if req.status == "Open"]

    # Filter requests based on substitute's preferences
    matching_requests = []
    
    # Constants for "All" grade and subject IDs
    ALL_GRADE_ID = 9  # ID for "All" grade
    ALL_SUBJECT_ID = 8  # ID for "All" subject

    for request, teacher_name, teacher in all_open_requests:
        # Get the set of grade IDs for the substitute and teacher
        sub_grade_ids = {grade.id for grade in logged_in_user.grades}
        teacher_grade_ids = {grade.id for grade in teacher.grades}

        # Get the set of subject IDs for the substitute and teacher
        sub_subject_ids = {subject.id for subject in logged_in_user.subjects}
        teacher_subject_ids = {subject.id for subject in teacher.subjects}

        # Rule 1: If substitute selected "All" for both grades and subjects
        if ALL_GRADE_ID in sub_grade_ids and ALL_SUBJECT_ID in sub_subject_ids:
            matching_requests.append((request, teacher_name, teacher))
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
        # Get the set of school IDs for the substitute and teacher
        sub_school_ids = {school.id for school in logged_in_user.schools}
        teacher_school_ids = {school.id for school in teacher.schools}
        
        # If substitute doesn't have any schools assigned, show all schools
        if not sub_school_ids:
            school_match = True
        # If teacher doesn't have any schools assigned, show to all substitutes
        elif not teacher_school_ids:
            school_match = True
        # If there's an overlap in schools
        elif sub_school_ids.intersection(teacher_school_ids):
            school_match = True
        # If request has a school_id and it's in the substitute's schools
        elif request.school_id and request.school_id in sub_school_ids:
            school_match = True
            
        # If grade, subject, and school match, add to matching requests
        if grade_match and subject_match and school_match:
            matching_requests.append((request, teacher_name, teacher))
    
    # Get unavailability data for the substitute
    unavailability = SubstituteUnavailability.query.filter_by(user_id=logged_in_user.id).all()
    
    # Convert to JSON-serializable format for passing to template
    unavailability_data = []
    for item in unavailability:
        unavailability_data.append({
            'id': item.id,
            'date': item.date.strftime('%Y-%m-%d'),
            'all_day': item.all_day,
            'time_range': item.time_range,
            'repeat_pattern': item.repeat_pattern,
            'repeat_until': item.repeat_until.strftime('%Y-%m-%d') if item.repeat_until else None
        })

    return render_template('substitute_dashboard.html', 
                          user=logged_in_user, 
                          accepted_requests=accepted_requests,
                          matching_requests=matching_requests,
                          unavailability_data=unavailability_data)


@app.route('/edit_profile/<int:user_id>', methods=['GET', 'POST'])
def edit_profile(user_id):
    # Ensure user is authenticated
    logged_in_user = get_logged_in_user()
    if not logged_in_user:
        flash('Please log in to continue.')
        return redirect(url_for('index'))

    # Get the user to edit
    user_to_edit = User.query.get_or_404(user_id)
    
    # Import the shared schools check function
    from blueprints.utils.shared_schools_check import check_shared_schools_access
    
    # Check permissions: user can edit their own profile or admin_l2 can edit profiles of users from shared schools
    if logged_in_user.id != user_to_edit.id and (logged_in_user.role != 'admin_l2' or not check_shared_schools_access(user_id)):
        flash('You do not have permission to edit this profile.')
        return redirect(url_for('user_profile', user_id=user_id))

    # Ensure user is a teacher, substitute, or admin_l2
    if logged_in_user.role not in ['teacher', 'substitute', 'admin_l2']:
        flash('This feature is only available for teachers, substitutes, and level 2 admins.')
        return redirect(url_for('dashboard'))

    # Fetch all grades, subjects, and schools for the form
    grades = Grade.query.order_by(Grade.id.asc()).all()
    subjects = Subject.query.order_by(Subject.id.asc()).all()
    schools = filter_by_organization(School.query, School).order_by(School.name.asc()).all()

    if request.method == 'POST':
        # Update user details
        user_to_edit.name = request.form['name']
        user_to_edit.email = request.form['email']
        user_to_edit.phone = request.form.get('phone', None)
        user_to_edit.timezone = request.form.get('timezone', 'UTC')  # Get timezone or default to UTC
        
        # Get multiple schools
        school_ids = request.form.getlist('schools')  # List of selected school IDs
        school_objs = School.query.filter(School.id.in_(school_ids)).all()

        # Update grades, subjects, and schools
        grade_ids = request.form.getlist('grades')  # List of selected grade IDs
        subject_ids = request.form.getlist('subjects')  # List of selected subject IDs
        grade_objs = Grade.query.filter(Grade.id.in_(grade_ids)).all()
        subject_objs = Subject.query.filter(Subject.id.in_(subject_ids)).all()

        user_to_edit.grades = grade_objs
        user_to_edit.subjects = subject_objs
        user_to_edit.schools = school_objs  # Update schools relationship

        # Save changes to the database
        db.session.commit()

        flash('Profile has been updated successfully!')

        # Redirect based on user role and who is being edited
        if logged_in_user.role == 'admin_l2' and logged_in_user.id != user_to_edit.id:
            return redirect(url_for('user_profile', user_id=user_id))
        elif user_to_edit.role == 'substitute':
            return redirect(url_for('substitute_dashboard'))
        else:
            return redirect(url_for('dashboard'))

    return render_template('edit_profile.html', user=user_to_edit, grades=grades, subjects=subjects, schools=schools)


@app.route('/dashboard')
def dashboard():
    """Dashboard for teachers."""
    logged_in_user = get_logged_in_user()
    if not logged_in_user:  # Redirect if user is not logged in
        return redirect(url_for('index'))
    past_bookings = (
        filter_by_organization(SubstituteRequest.query, SubstituteRequest)
        .filter_by(teacher_id=logged_in_user.id)
        .order_by(SubstituteRequest.date.desc())
        .all()
    )
    
    # Calculate total hours out
    from helpers import calculate_total_hours_out
    total_hours_out = calculate_total_hours_out(past_bookings)
    
    return render_template('dashboard.html', user=logged_in_user, past_bookings=past_bookings, total_hours_out=total_hours_out)


@app.route('/lottie_debug')
def lottie_debug():
    """Debug page for testing Lottie animations."""
    # No authentication required for easy testing
    return render_template('sub_request_debug.html')


@app.route('/api/unavailability', methods=['GET', 'POST'])
def api_unavailability():
    """API endpoint to get and save substitute unavailability."""
    logged_in_user = get_logged_in_user()
    if not logged_in_user:
        return jsonify({"error": "Not authenticated"}), 401
    
    if logged_in_user.role != 'substitute':
        return jsonify({"error": "Only substitutes can access this endpoint"}), 403
    
    if request.method == 'GET':
        # Get all unavailability records for the substitute
        unavailability = SubstituteUnavailability.query.filter_by(user_id=logged_in_user.id).all()
        
        # Convert to JSON-serializable format
        result = []
        for item in unavailability:
            result.append({
                'id': item.id,
                'date': item.date.strftime('%Y-%m-%d'),
                'all_day': item.all_day,
                'time_range': item.time_range,
                'repeat_pattern': item.repeat_pattern,
                'repeat_until': item.repeat_until.strftime('%Y-%m-%d') if item.repeat_until else None
            })
        
        return jsonify(result)
    
    elif request.method == 'POST':
        # Get data from request
        data = request.json
        
        # Validate required fields
        if 'date' not in data:
            return jsonify({"error": "Date is required"}), 400
        
        # Create new unavailability record
        try:
            new_unavailability = SubstituteUnavailability(
                user_id=logged_in_user.id,
                date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
                all_day=data.get('all_day', True),
                time_range=data.get('time_range'),
                repeat_pattern=data.get('repeat_pattern'),
                repeat_until=datetime.strptime(data['repeat_until'], '%Y-%m-%d').date() if data.get('repeat_until') else None
            )
            
            db.session.add(new_unavailability)
            db.session.commit()
            
            return jsonify({"message": "Unavailability saved successfully", "id": new_unavailability.id})
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving unavailability: {e}")
            return jsonify({"error": "Error saving unavailability"}), 500


@app.route('/api/unavailability/<int:unavailability_id>', methods=['DELETE'])
def api_delete_unavailability(unavailability_id):
    """API endpoint to delete substitute unavailability."""
    logged_in_user = get_logged_in_user()
    if not logged_in_user:
        return jsonify({"error": "Not authenticated"}), 401
    
    if logged_in_user.role != 'substitute':
        return jsonify({"error": "Only substitutes can access this endpoint"}), 403
    
    # Get the unavailability record
    unavailability = SubstituteUnavailability.query.filter_by(id=unavailability_id, user_id=logged_in_user.id).first()
    
    if not unavailability:
        return jsonify({"error": "Unavailability record not found"}), 404
    
    try:
        db.session.delete(unavailability)
        db.session.commit()
        return jsonify({"message": "Unavailability deleted successfully"})
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting unavailability: {e}")
        return jsonify({"error": "Error deleting unavailability"}), 500


@app.route('/api/teacher_bookings')
def api_teacher_bookings():
    """API endpoint to get teacher bookings for reactive dashboard."""
    logged_in_user = get_logged_in_user()
    if not logged_in_user:
        return jsonify({"error": "Not authenticated"}), 401

    # Get all bookings for the teacher
    bookings = SubstituteRequest.query.filter_by(teacher_id=logged_in_user.id).order_by(SubstituteRequest.date.desc()).all()

    # Calculate total hours out
    from helpers import calculate_total_hours_out
    total_hours_out = calculate_total_hours_out(bookings)

    # Convert bookings to JSON-serializable format
    bookings_data = []
    for booking in bookings:
        # Get user's timezone or default to UTC
        user_timezone = logged_in_user.timezone or 'UTC'
        
        # Convert created_at to user's timezone
        from helpers import convert_utc_to_local, format_datetime
        local_created_at = convert_utc_to_local(booking.created_at, user_timezone)
        
        booking_data = {
            "id": booking.id,
            "date": booking.date.strftime('%Y-%m-%d'),
            "date_formatted": booking.date.strftime('%B %d, %Y'),
            "time": booking.time,
            "status": booking.status,
            "details": booking.details,
            "created_at": booking.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            "created_at_formatted": format_datetime(local_created_at, '%B %d, %Y at %I:%M %p'),
            "timezone": user_timezone,
        }

        # Add substitute info if available
        if booking.status != "Open" and booking.substitute_user:
            booking_data["substitute"] = {
                "id": booking.substitute_user.id,
                "name": booking.substitute_user.name
            }

        bookings_data.append(booking_data)

    return jsonify({"bookings": bookings_data, "total_hours_out": total_hours_out})


@app.route('/admin_dashboard', methods=['GET'])
@requires_role('admin')
def admin_dashboard():
    """Dashboard for admins."""
    # Get the logged-in user to determine admin level
    logged_in_user = get_logged_in_user()
    is_tech_coordinator_value = is_tech_coordinator(logged_in_user)

    # Get all teachers for the create request form and display
    teachers = User.query.filter_by(role='teacher').order_by(User.name).all()

    # Get all grades and subjects for the form
    grades = Grade.query.order_by(Grade.id.asc()).all()
    subjects = Subject.query.order_by(Subject.id.asc()).all()

    # Get search parameters from request
    search_keyword = request.args.get('search_keyword', '')
    search_date = request.args.get('search_date', '')
    search_status = request.args.get('search_status', '')

    # Create aliases for the User table to distinguish between teachers and substitutes
    TeacherUser = aliased(User)
    SubstituteUser = aliased(User)

    # Start with a base query that joins with User table for both teacher and substitute
    # This avoids multiple separate queries and joins
    base_query = db.session.query(SubstituteRequest).\
        join(TeacherUser, SubstituteRequest.teacher_id == TeacherUser.id).\
        outerjoin(SubstituteUser, SubstituteRequest.substitute_id == SubstituteUser.id)

    filters = []

    # Apply filters based on search parameters
    if search_keyword:
        # Search by teacher or substitute name in a single query
        name_filter = db.or_(
            TeacherUser.name.ilike(f'%{search_keyword}%'),
            SubstituteUser.name.ilike(f'%{search_keyword}%')
        )
        filters.append(name_filter)

    # Filter by date if provided
    if search_date:
        try:
            search_date_obj = datetime.strptime(search_date, '%m/%d/%Y').date()
            filters.append(SubstituteRequest.date == search_date_obj)
        except ValueError:
            # If date format is invalid, ignore this filter
            pass

    # Filter by status if provided
    if search_status:
        filters.append(SubstituteRequest.status == search_status)
        
    # Filter by school for level 2 admins
    if logged_in_user.role == 'admin_l2' and logged_in_user.schools:
        # Level 2 admins should only see requests from their schools
        # Get the admin's school IDs
        admin_school_ids = [school.id for school in logged_in_user.schools]
        
        # Get all teachers who share at least one school with the admin
        teachers_in_admin_schools = User.query.filter(
            User.role == 'teacher',
            User.schools.any(School.id.in_(admin_school_ids))
        ).all()
        
        # Get the IDs of these teachers
        teacher_ids = [teacher.id for teacher in teachers_in_admin_schools]
        
        # Filter requests to only include those from these teachers or with no school
        if teacher_ids:
            school_filter = db.or_(
                SubstituteRequest.teacher_id.in_(teacher_ids),
                SubstituteRequest.school_id == None
            )
            filters.append(school_filter)
        else:
            # If no teachers match, only show requests with no school
            filters.append(SubstituteRequest.school_id == None)

    # Apply all filters to the query
    if filters:
        for f in filters:
            base_query = base_query.filter(f)

    # If no search parameters are provided, separate by recent/older
    if not (search_keyword or search_date or search_status):
        # Import the utility function for getting current time in timezone
        from time_utils import get_current_time_in_timezone
        
        # Get the user's timezone or default to UTC
        user_timezone = logged_in_user.timezone if hasattr(logged_in_user, 'timezone') else 'UTC'
        
        # Get current time in user's timezone and calculate cutoff date
        current_time = get_current_time_in_timezone(user_timezone)
        cutoff_date = (current_time - timedelta(days=15)).date()
        
        recent_requests = base_query.filter(
            SubstituteRequest.date >= cutoff_date
        ).order_by(SubstituteRequest.date.asc()).all()
        older_requests = base_query.filter(
            SubstituteRequest.date < cutoff_date
        ).order_by(SubstituteRequest.date.desc()).all()
    else:
        # If search parameters are provided, show all matching results as recent
        recent_requests = base_query.order_by(SubstituteRequest.date.desc()).all()
        older_requests = []

    return render_template(
        'admin_dashboard.html',
        user=logged_in_user,
        recent_requests=recent_requests,
        older_requests=older_requests,
        teachers=teachers,
        grades=grades,
        subjects=subjects,
        is_tech_coordinator_value=is_tech_coordinator_value,  # Pass this to the template
        request=request  # Pass the request object to access args in the template
    )


@app.route('/admin_request', methods=['GET'])
@requires_role('admin')
def admin_request_form():
    """Display the form for admins to create substitute requests."""
    
    # Import the filter_by_shared_schools function
    from blueprints.utils.utils import filter_by_shared_schools
    
    # Get teachers for the dropdown, filtered by shared schools for level 2 admins
    teachers_query = User.query.filter_by(role='teacher')
    
    # Apply the shared schools filter for level 2 admins
    teachers_query = filter_by_shared_schools(teachers_query, User)
    
    # Get the final list of teachers, ordered by name
    teachers = teachers_query.order_by(User.name).all()
    
    return render_template('admin_request.html', teachers=teachers)


@app.route('/admin_create_request', methods=['POST'])
@requires_role('admin')
@limiter.limit("10 per minute")
def admin_create_request():
    """Handle admin creation of substitute requests."""

    try:
        # Get form data
        teacher_id = request.form['teacher_id']
        date = request.form['date']
        time = request.form['time']
        details = request.form.get('details', '')
        reason = request.form.get('reason', '')
        grade_id = request.form.get('grade_id')
        subject_id = request.form.get('subject_id')
        
        # Validate that the date and time are in the future and not on a weekend
        from helpers import is_future_date_time
        # Get the logged-in user for timezone-aware validation
        logged_in_user = User.query.filter_by(id=session.get('user_id')).first()
        if not is_future_date_time(date, time, logged_in_user):
            flash('Error: Substitute requests can only be created for future weekdays (Monday-Friday).')
            return redirect(url_for('admin_request_form'))

        # Validate teacher exists
        teacher = User.query.filter_by(id=teacher_id, role='teacher').first()
        if not teacher:
            flash('Invalid teacher selected.')
            return redirect(url_for('admin_dashboard'))
            
        # For level 2 admins, check if the teacher belongs to one of their assigned schools
        if logged_in_user.role == 'admin_l2' and logged_in_user.schools:
            # Get the admin's school IDs
            admin_school_ids = [school.id for school in logged_in_user.schools]
            
            # Check if the teacher shares at least one school with the admin
            teacher_school_ids = [school.id for school in teacher.schools]
            if not any(school_id in admin_school_ids for school_id in teacher_school_ids):
                flash('Error: You can only create requests for teachers in your assigned schools.')
                return redirect(url_for('admin_dashboard'))
            
        # If grade_id is not provided, try to get it from the teacher's profile
        if not grade_id and teacher.grades:
            # If teacher has only one grade, use that grade
            if len(teacher.grades) == 1:
                grade_id = teacher.grades[0].id
            # Otherwise, use the first grade (if any)
            elif len(teacher.grades) > 1:
                grade_id = teacher.grades[0].id
                
        # If subject_id is not provided, try to get it from the teacher's profile
        if not subject_id and teacher.subjects:
            # If teacher has only one subject, use that subject
            if len(teacher.subjects) == 1:
                subject_id = teacher.subjects[0].id
            # Otherwise, use the first subject (if any)
            elif len(teacher.subjects) > 1:
                subject_id = teacher.subjects[0].id

        # Generate unique token
        token = str(uuid.uuid4())

        # Get teacher's first school if available
        teacher_school_id = None
        if teacher and teacher.schools:
            teacher_school_id = teacher.schools[0].id
            
        # Create and save substitute request
        # Parse the date and ensure it's stored as a date object (not datetime)
        parsed_date = datetime.strptime(date, '%m/%d/%Y').date()
        
        sub_request = SubstituteRequest(
            teacher_id=teacher_id,
            date=parsed_date,
            time=time,
            details=details.strip(),
            reason=reason,
            grade_id=grade_id,
            subject_id=subject_id,
            school_id=teacher_school_id,
            organization_id=teacher.organization_id,
            token=token
        )
        db.session.add(sub_request)
        db.session.commit()

        # Generate dynamic link
        request_link = url_for('view_sub_request', token=token, _external=True)

        # Use the helper function to filter eligible substitutes at the database level
        from helpers import filter_eligible_substitutes
        # Convert date string to datetime.date object for availability checking
        request_date = datetime.strptime(date, '%m/%d/%Y').date()
        eligible_substitutes = filter_eligible_substitutes(teacher, request_date=request_date, request_time=time, school_id=teacher_school_id)

        # Get grade and subject names
        grade_name = "Not specified"
        subject_name = "Not specified"
        if grade_id:
            grade = Grade.query.get(grade_id)
            if grade:
                grade_name = grade.name
        if subject_id:
            subject = Subject.query.get(subject_id)
            if subject:
                subject_name = subject.name

        # Import the background threading utility
        from threading_utils import run_in_background
        from helpers import send_email, send_sms

        # Send notification with link to eligible substitutes
        for substitute in eligible_substitutes:
            # Use centralized template function
            email_subject, email_body = generate_substitute_notification_email(
                teacher, date, time, grade_name, subject_name, details, request_link
            )
            # Run email sending in background thread
            run_in_background(send_email, email_subject, substitute.email, email_body)

            # Send SMS to eligible substitutes with phones
            if substitute.phone:
                sms_body = generate_substitute_notification_sms(teacher, date, time, grade_name, subject_name, request_link)
                # Run SMS sending in background thread
                run_in_background(send_sms, substitute.phone, sms_body)

        # Send notification to admin via email
        admin_subject, admin_email_body = generate_admin_notification_email(
            teacher, date, time, grade_name, subject_name, details, reason
        )
            
        # Send to level 2 admins associated with the same schools as the teacher
        # This ensures notifications are only sent to admins who are responsible for the teacher
        # If teacher has no schools, no notifications are sent
        if teacher and teacher.schools:
            # Get all school IDs associated with the teacher
            teacher_school_ids = [school.id for school in teacher.schools]
            
            # Filter level 2 admins who share at least one school with the teacher
            level2_admins = User.query.filter_by(role='admin_l2').join(
                user_schools, User.id == user_schools.c.user_id
            ).filter(
                user_schools.c.school_id.in_(teacher_school_ids)
            ).distinct().all()
            
            for admin in level2_admins:
                # Run email sending in background thread
                run_in_background(send_email, admin_subject, admin.email, admin_email_body)

        # Send SMS notification to admin
        admin_sms_body = generate_admin_notification_sms(teacher, date, time, grade_name, subject_name, reason)
        
        # Use the same level 2 admins filtered by schools as for email notifications
        # If teacher has no schools or level2_admins is not defined, no SMS notifications are sent
        if teacher and teacher.schools and 'level2_admins' in locals():
            # We already have level2_admins filtered by teacher's schools from the email notification section
            for admin in level2_admins:
                if admin.phone:  # Only send if admin has a phone number
                    # Run SMS sending in background thread
                    run_in_background(send_sms, admin.phone, admin_sms_body)

        # Send email notification to teacher
        teacher_subject, teacher_email_body = generate_teacher_confirmation_email(
            date, time, grade_name, subject_name, details, reason
        )
        if teacher.email:
            # Run email sending in background thread
            run_in_background(send_email, teacher_subject, teacher.email, teacher_email_body)

        # Send SMS confirmation to teacher
        if teacher.phone:
            teacher_sms_body = generate_teacher_confirmation_sms(date, time)
            # Run SMS sending in background thread
            run_in_background(send_sms, teacher.phone, teacher_sms_body)

        flash('Substitute request created successfully! Notification sent to matching substitutes.')

    except Exception as e:
        flash('An error occurred while creating the request.')
        logger.error(f"Error: {e}")

    return redirect(url_for('admin_dashboard'))


@app.route('/request', methods=['GET', 'POST'])
def request_form_and_submit():
    if request.method == 'GET':
        # Get the logged-in user to pass to the template
        logged_in_user = get_logged_in_user()
        if not logged_in_user:
            return redirect(url_for('index'))
        return render_template('request.html', user=logged_in_user)

    elif request.method == 'POST':
        if 'user_info' not in session:
            return redirect(url_for('index'))

        try:
            date = request.form['date']
            time = request.form['time']
            details = request.form.get('details', '')
            reason = request.form.get('reason', '')

            # Validate that the date and time are in the future and not on a weekend
            from helpers import is_future_date_time
            if not is_future_date_time(date, time):
                flash('Error: Substitute requests can only be created for future weekdays (Monday-Friday).')
                return redirect(url_for('request_form_and_submit'))

            teacher = get_logged_in_user()

            if teacher:
                token = str(uuid.uuid4())  # Generate unique token

                # Get grade and subject IDs from the form or auto-select from teacher's profile
                grade_id = request.form.get('grade_id')
                subject_id = request.form.get('subject_id')
                
                # For teachers, automatically use their first grade
                if not grade_id and teacher.grades:
                    grade_id = teacher.grades[0].id
                elif not grade_id:
                    flash('Error: No grade associated with your account.')
                    return redirect(url_for('request_form_and_submit'))
                
                # For teachers, automatically use their first subject
                if not subject_id and teacher.subjects:
                    subject_id = teacher.subjects[0].id
                elif not subject_id:
                    flash('Error: No subject associated with your account.')
                    return redirect(url_for('request_form_and_submit'))

                try:
                    # Create and save substitute request
                    # Get teacher's first school if available
                    teacher_school_id = None
                    if teacher.schools:
                        teacher_school_id = teacher.schools[0].id
                        
                    sub_request = SubstituteRequest(
                        teacher_id=teacher.id,
                        date=datetime.strptime(date, '%m/%d/%Y'),
                        time=time,
                        details=details.strip(),
                        reason=reason,
                        grade_id=grade_id,
                        subject_id=subject_id,
                        school_id=teacher_school_id,  # Use teacher's first school
                        organization_id=teacher.organization_id,
                        token=token
                    )
                    db.session.add(sub_request)
                    db.session.commit()
                except ValueError as e:
                    flash('Invalid date format. Please use MM/DD/YYYY format.')
                    logger.error(f"Date parsing error: {e}")
                    return redirect(url_for('request_form_and_submit'))
                except sqlalchemy.exc.SQLAlchemyError as e:
                    flash('Database error while saving request.')
                    logger.error(f"Database error: {e}")
                    return redirect(url_for('dashboard'))

                # **Generate dynamic link**
                request_link = url_for('view_sub_request', token=token, _external=True)

                # Use the helper function to filter eligible substitutes at the database level
                from helpers import filter_eligible_substitutes
                from helpers import send_email, send_sms
                from threading_utils import run_in_background
                
                # Convert date string to datetime.date object for availability checking
                request_date = datetime.strptime(date, '%m/%d/%Y').date()
                eligible_substitutes = filter_eligible_substitutes(teacher, request_date=request_date, request_time=time, school_id=teacher_school_id)

                # **Send notification with link to eligible substitutes**
                email_subject = "New Substitute Request Available"

                # Get grade and subject names
                grade_name = "Not specified"
                subject_name = "Not specified"
                if grade_id:
                    grade = Grade.query.get(grade_id)
                    if grade:
                        grade_name = grade.name
                if subject_id:
                    subject = Subject.query.get(subject_id)
                    if subject:
                        subject_name = subject.name
                        
                for substitute in eligible_substitutes:
                    # Use centralized template function
                    email_subject, email_body = generate_substitute_notification_email(
                        teacher, date, time, grade_name, subject_name, details, request_link
                    )
                    # Run email sending in background thread
                    run_in_background(send_email, email_subject, substitute.email, email_body)
                    
                    # Send SMS to eligible substitutes with phones
                    if substitute.phone:
                        sms_body = generate_substitute_notification_sms(teacher, date, time, grade_name, subject_name, request_link)
                        # Run SMS sending in background thread
                        run_in_background(send_sms, substitute.phone, sms_body)

                # Send notification to admin via email
                admin_subject, admin_email_body = generate_admin_notification_email(
                    teacher, date, time, grade_name, subject_name, details, reason
                )
                
                # Send to level 2 admins associated with the same schools as the teacher
                # This ensures notifications are only sent to admins who are responsible for the teacher
                # If teacher has no schools, no notifications are sent
                if teacher and teacher.schools:
                    # Get all school IDs associated with the teacher
                    teacher_school_ids = [school.id for school in teacher.schools]
                    
                    # Filter level 2 admins who share at least one school with the teacher
                    level2_admins = User.query.filter_by(role='admin_l2').join(
                        user_schools, User.id == user_schools.c.user_id
                    ).filter(
                        user_schools.c.school_id.in_(teacher_school_ids)
                    ).distinct().all()
                    
                    # Generate SMS body once outside the loop
                    admin_sms_body = generate_admin_notification_sms(teacher, date, time, grade_name, subject_name, reason)
                    
                    for admin in level2_admins:
                        # Run email sending in background thread
                        run_in_background(send_email, admin_subject, admin.email, admin_email_body)
                        
                        # Send SMS notification to admin if they have a phone number
                        if admin.phone:
                            # Run SMS sending in background thread
                            run_in_background(send_sms, admin.phone, admin_sms_body)

                # Send email notification to teacher
                teacher_subject, teacher_email_body = generate_teacher_confirmation_email(
                    date, time, grade_name, subject_name, details, reason
                )
                if teacher.email:
                    # Run email sending in background thread
                    run_in_background(send_email, teacher_subject, teacher.email, teacher_email_body)

                # Send SMS confirmation to teacher
                if teacher.phone:
                    teacher_sms_body = generate_teacher_confirmation_sms(date, time)
                    # Run SMS sending in background thread
                    run_in_background(send_sms, teacher.phone, teacher_sms_body)

                flash('Substitute request submitted successfully! Notification sent to matching substitutes.')
            else:
                flash('Error: Could not find your user account.')

        except KeyError as e:
            flash('Missing required field in form submission.')
            logger.error(f"Form field error: {e}")
            return redirect(url_for('request_form_and_submit'))
        except Exception as e:
            flash('An error occurred while submitting the request.')
            logger.error(f"Unexpected error: {e}")

        return redirect(url_for('dashboard'))


@app.route('/sub_request/<token>', methods=['GET', 'POST'])
def view_sub_request(token):
    # Ensure user is logged in
    if 'user_info' not in session:
        flash("Please log in to continue.")
        return redirect(url_for('login'))  # Redirect to login page

    sub_request = SubstituteRequest.query.filter_by(token=token).first()

    if not sub_request:
        flash("Invalid or expired request.")
        return redirect(url_for('index'))

    # Fetch the teacher information
    teacher = User.query.get(sub_request.teacher_id)

    # Handle POST request (Accept button click)
    if request.method == 'POST' and sub_request.status == "Open":
        logged_in_user = get_logged_in_user()

        # Ensure only substitutes can accept the request
        if not logged_in_user or logged_in_user.role != "substitute":
            flash("Unauthorized action.")
            return redirect(url_for('view_sub_request', token=token))

        sub_request.status = "Filled"
        sub_request.substitute_id = logged_in_user.id
        db.session.commit()

        # Send email notifications
        # Import helper functions for email templates and background threading
        from helpers import generate_admin_sub_filled_email, generate_teacher_sub_filled_email, generate_substitute_confirmation_email, send_email
        from threading_utils import run_in_background

        # 1. Email to level 2 admins associated with the same school as the request
        # This ensures notifications are only sent to admins who are responsible for the specific school
        # If no school is specified, no notifications are sent
        admin_subject, admin_email_body = generate_admin_sub_filled_email(teacher, sub_request, logged_in_user)
        
        # Get the school ID from the substitute request
        school_id = sub_request.school_id
        
        if school_id:
            # Filter level 2 admins by school using the user_schools association table
            # This targets notifications only to admins associated with this school
            level2_admins = User.query.filter_by(role='admin_l2').join(
                user_schools, User.id == user_schools.c.user_id
            ).filter(
                user_schools.c.school_id == school_id
            ).all()
            
            for admin in level2_admins:
                # Run email sending in background thread
                run_in_background(send_email, admin_subject, admin.email, admin_email_body)

        # 2. Email to teacher
        teacher_subject, teacher_email_body = generate_teacher_sub_filled_email(sub_request, logged_in_user)
        # Run email sending in background thread
        run_in_background(send_email, teacher_subject, teacher.email, teacher_email_body)

        # 3. Email to substitute
        sub_subject, sub_email_body = generate_substitute_confirmation_email(teacher, sub_request)
        # Run email sending in background thread
        run_in_background(send_email, sub_subject, logged_in_user.email, sub_email_body)
        
        # Send SMS to substitute if they have a phone number
        if logged_in_user.phone:
            sub_sms_body = generate_substitute_confirmation_sms(teacher, sub_request)
            run_in_background(send_sms, logged_in_user.phone, sub_sms_body)

        flash("You have successfully accepted the sub request.")
        return redirect(url_for('view_sub_request', token=token))

    # Get the logged-in user to determine if they are the one who accepted the request
    logged_in_user = get_logged_in_user()

    # Get the substitute who accepted the request (if any)
    substitute = None
    if sub_request.substitute_id:
        substitute = User.query.get(sub_request.substitute_id)

    return render_template('sub_request.html', 
                          sub_request=sub_request, 
                          teacher=teacher, 
                          logged_in_user=logged_in_user,
                          substitute=substitute)


@app.route('/manage_admins', methods=['GET'])
@requires_role('admin_l1')
def manage_admins():
    """Route for tech coordinators to manage level 2 admins."""
    
    # Get all level 2 admins (filtered by organization)
    admins = filter_by_organization(User.query, User).filter_by(role='admin_l2').order_by(User.name).all()
    
    # Fetch schools from the database (filtered by organization)
    schools = filter_by_organization(School.query, School).order_by(School.name.asc()).all()
    
    return render_template(
        'manage_admins.html',
        admins=admins,
        schools=schools,
        user=session['user_info']
    )


@app.route('/add_admin', methods=['POST'])
@requires_role('admin_l1')
@limiter.limit("10 per minute")
def add_admin():
    """Route for tech coordinators to create level 2 admin accounts."""
    
    # Get form data
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    admin_type = request.form.get('admin_type', 'front_office')  # front_office or principal
    
    # Get selected schools (filtered by organization)
    school_ids = request.form.getlist('schools')  # List of selected school IDs
    school_objs = filter_by_organization(School.query, School).filter(School.id.in_(school_ids)).all()
    
    # Validate required inputs
    if not name or not email:
        flash('Name and email are required!')
        return redirect(url_for('manage_admins'))
    
    # Check for duplicate email
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        flash('A user with this email already exists!')
        return redirect(url_for('manage_admins'))
    
    # Create the new admin user
    logged_in_user = get_logged_in_user()
    new_admin = User(
        name=name,
        email=email,
        role='admin_l2',
        phone=phone,
        created_by=logged_in_user.id if logged_in_user else None,
        organization_id=logged_in_user.organization_id if logged_in_user else None
    )
    
    # Assign schools to the new admin
    new_admin.schools.extend(school_objs)
    
    # Add and commit changes to the database
    db.session.add(new_admin)
    db.session.commit()
    
    # Flash a success message
    flash(f'Admin {name} ({email}) added successfully!')
    
    return redirect(url_for('manage_admins'))


@app.route('/manage_users', methods=['GET'])
@requires_role('admin')
def manage_users():
    # User authentication is handled by the requires_role decorator

    # Get sort parameters from query string
    sort_by = request.args.get('sort_by', 'id')
    sort_order = request.args.get('sort_order', 'asc')

    # Import the filter_by_shared_schools function
    from blueprints.utils.utils import filter_by_shared_schools

    # Base queries for teachers and substitutes (filtered by organization)
    teachers_query = filter_by_organization(User.query, User).filter_by(role='teacher')
    substitutes_query = filter_by_organization(User.query, User).filter_by(role='substitute')
    
    # Apply the shared schools filter for level 2 admins
    teachers_query = filter_by_shared_schools(teachers_query, User)
    substitutes_query = filter_by_shared_schools(substitutes_query, User)

    # Initialize teachers and substitutes with default values
    # in case there's an error in the sorting logic
    teachers = teachers_query.all()
    substitutes = substitutes_query.all()

    # Handle sorting based on sort_by parameter
    if sort_by == 'name':
        sort_attr = User.name
    elif sort_by == 'email':
        sort_attr = User.email
    elif sort_by == 'grade':
        # For grade sorting, we'll need to handle it differently
        # First, get all users with their first grade name
        from sqlalchemy import func, case, select
        from sqlalchemy.orm import aliased

        # Get the first grade name for each user
        grade_alias = aliased(Grade)
        grade_subq = (
            select(
                user_grades.c.user_id,
                func.min(grade_alias.name).label('first_grade_name')
            )
            .select_from(
                user_grades.join(
                    grade_alias,
                    user_grades.c.grade_id == grade_alias.id
                )
            )
            .group_by(user_grades.c.user_id)
            .alias('grade_subq')
        )

        # Apply sorting to both queries
        teachers_query = teachers_query.outerjoin(
            grade_subq,
            User.id == grade_subq.c.user_id
        ).order_by(
            grade_subq.c.first_grade_name.desc() if sort_order == 'desc' else grade_subq.c.first_grade_name
        )

        substitutes_query = substitutes_query.outerjoin(
            grade_subq,
            User.id == grade_subq.c.user_id
        ).order_by(
            grade_subq.c.first_grade_name.desc() if sort_order == 'desc' else grade_subq.c.first_grade_name
        )

        # Execute queries
        teachers = teachers_query.all()
        substitutes = substitutes_query.all()
    elif sort_by == 'subject':
        # For subject sorting, similar to grade sorting
        from sqlalchemy import func, case, select
        from sqlalchemy.orm import aliased

        # Get the first subject name for each user
        subject_alias = aliased(Subject)
        subject_subq = (
            select(
                user_subjects.c.user_id,
                func.min(subject_alias.name).label('first_subject_name')
            )
            .select_from(
                user_subjects.join(
                    subject_alias,
                    user_subjects.c.subject_id == subject_alias.id
                )
            )
            .group_by(user_subjects.c.user_id)
            .alias('subject_subq')
        )

        # Apply sorting to both queries
        teachers_query = teachers_query.outerjoin(
            subject_subq,
            User.id == subject_subq.c.user_id
        ).order_by(
            subject_subq.c.first_subject_name.desc() if sort_order == 'desc' else subject_subq.c.first_subject_name
        )

        substitutes_query = substitutes_query.outerjoin(
            subject_subq,
            User.id == subject_subq.c.user_id
        ).order_by(
            subject_subq.c.first_subject_name.desc() if sort_order == 'desc' else subject_subq.c.first_subject_name
        )

        # Execute queries
        teachers = teachers_query.all()
        substitutes = substitutes_query.all()
    else:  # Default to id or other simple columns
        sort_attr = User.id if sort_by == 'id' else getattr(User, sort_by, User.id)

        # Apply sort order
        if sort_order == 'desc':
            sort_attr = sort_attr.desc()
        else:
            sort_attr = sort_attr.asc()

        # Execute queries with sorting
        teachers = teachers_query.order_by(sort_attr).all()
        substitutes = substitutes_query.order_by(sort_attr).all()

    # Fetch all grades, subjects, and schools from the database
    grades = Grade.query.order_by(Grade.id.asc()).all()
    subjects = Subject.query.order_by(Subject.id.asc()).all()
    schools = School.query.order_by(School.name.asc()).all()

    # Render the template, passing the required data
    return render_template(
        'manage_users.html',
        teachers=teachers,
        substitutes=substitutes,
        grades=grades,
        subjects=subjects,
        schools=schools,
        user=session['user_info'],
        sort_by=sort_by,
        sort_order=sort_order,
        errors={},  # Add empty errors object to prevent Jinja2 from throwing an error
        formData={
            'grades': [], 
            'subjects': [], 
            'schools': [],
            'name': '',
            'email': '',
            'role': 'teacher',  # Default role
            'phone': '',
            'userId': ''
        }  # Initialize all formData properties to prevent Jinja2 errors
    )


@app.route('/sub_request/<token>/accept', methods=['POST'])
def accept_sub_request(token):
    try:
        sub_request = SubstituteRequest.query.filter_by(token=token).first()

        if not sub_request:
            return jsonify({"status": "error", "message": "Invalid request"}), 404

        if sub_request.status != "Open":
            return jsonify({"status": "error", "message": "This position has already been filled"}), 400

        # Assign the logged-in user (substitute) to the request
        logged_in_user = get_logged_in_user()
        if not logged_in_user or logged_in_user.role != "substitute":
            return jsonify({"status": "error", "message": "Unauthorized action"}), 403

        try:
            sub_request.status = "Filled"
            sub_request.substitute_id = logged_in_user.id
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error when updating substitute request: {e}")
            return jsonify({"status": "error", "message": "Database error occurred. Please try again."}), 500

        try:
            # Fetch the teacher information
            teacher = User.query.get(sub_request.teacher_id)
            if not teacher:
                logger.error(f"Teacher with ID {sub_request.teacher_id} not found")
                return jsonify({"status": "error", "message": "Teacher information not found"}), 500

            # Import helper functions for email templates, email/SMS sending, and background threading
            from helpers import generate_admin_sub_filled_email, generate_teacher_sub_filled_email, generate_substitute_confirmation_email, send_email, send_sms
            from threading_utils import run_in_background
            from pdf_handler import generate_absence_form_data, fill_absence_form

            # 1. Email to level 2 admins associated with the same school as the request
            # This ensures notifications are only sent to admins who are responsible for the specific school
            # If no school is specified, no notifications are sent
            admin_subject, admin_email_body = generate_admin_sub_filled_email(teacher, sub_request, logged_in_user)
            
            # Get the school ID from the substitute request
            school_id = sub_request.school_id
            
            # SMS notification is shorter due to character limitations
            from helpers import generate_admin_sub_filled_sms
            admin_sms_body = generate_admin_sub_filled_sms(teacher, sub_request, logged_in_user.name)
            
            if school_id:
                # Filter level 2 admins by school using the user_schools association table
                # This targets notifications only to admins associated with this school
                level2_admins = User.query.filter_by(role='admin_l2').join(
                    user_schools, User.id == user_schools.c.user_id
                ).filter(
                    user_schools.c.school_id == school_id
                ).all()
                
                for admin in level2_admins:
                    # Run email sending in background thread
                    run_in_background(send_email, admin_subject, admin.email, admin_email_body)
                    
                    # Run SMS sending in background thread if phone number is available
                    if admin.phone:
                        run_in_background(send_sms, admin.phone, admin_sms_body)

            # 2. Email to teacher
            teacher_subject, teacher_email_body = generate_teacher_sub_filled_email(sub_request, logged_in_user)
            # Run email sending in background thread
            run_in_background(send_email, teacher_subject, teacher.email, teacher_email_body)

            # Send SMS to teacher if phone number is available
            from message_templates import generate_teacher_sub_filled_sms
            if teacher.phone:
                teacher_sms_body = generate_teacher_sub_filled_sms(sub_request, logged_in_user.name)
                run_in_background(send_sms, teacher.phone, teacher_sms_body)

            # 3. Email to substitute
            sub_subject, sub_email_body = generate_substitute_confirmation_email(teacher, sub_request)
            # Run email sending in background thread
            run_in_background(send_email, sub_subject, logged_in_user.email, sub_email_body)
            
            # Send SMS to substitute if they have a phone number
            if logged_in_user.phone:
                sub_sms_body = generate_substitute_confirmation_sms(teacher, sub_request)
                run_in_background(send_sms, logged_in_user.phone, sub_sms_body)
            
            # Generate and fill absence report PDF in background thread
            def generate_pdf_in_background():
                try:
                    # Format the date for the PDF filename (YYYY-MM-DD)
                    request_date = sub_request.date.strftime("%Y-%m-%d")
                    
                    # Generate form data from the request
                    form_data = generate_absence_form_data(sub_request, teacher, logged_in_user)
                    
                    # Fill the PDF form
                    pdf_path = fill_absence_form(teacher.name, request_date, form_data)
                    
                    logger.info(f"Absence report PDF generated successfully: {pdf_path}")
                except Exception as e:
                    logger.error(f"Error generating absence report PDF: {e}")
            
            # Run PDF generation in background thread
            run_in_background(generate_pdf_in_background)

            return jsonify({"status": "success", "message": "Position accepted!"})
            
        except Exception as e:
            logger.error(f"Error in accept_sub_request after database commit: {e}")
            # Even if notifications fail, the request has been accepted, so return success
            return jsonify({"status": "success", "message": "Position accepted! (Notification error occurred)"}), 200
            
    except Exception as e:
        logger.error(f"Unexpected error in accept_sub_request: {e}")
        return jsonify({"status": "error", "message": "An unexpected error occurred. Please try again."}), 500


@app.route('/add_user', methods=['POST'])
@limiter.limit("10 per minute")
def add_user():
    try:
        # Get form data
        name = request.form.get('name')
        email = request.form.get('email')
        role = request.form.get('role')
        phone = request.form.get('phone')

        # Log the form data for debugging
        logger.info(f"Add user form data: name={name}, email={email}, role={role}, phone={phone}")

        # Collect multiple grades, subjects, and schools from checkboxes
        grade_ids = request.form.getlist('grades')  # List of selected grade IDs
        subject_ids = request.form.getlist('subjects')  # List of selected subject IDs
        school_ids = request.form.getlist('schools')  # List of selected school IDs

        # Log the selected IDs for debugging
        logger.info(f"Selected IDs: grades={grade_ids}, subjects={subject_ids}, schools={school_ids}")

        # Validate required inputs
        if not name or not email or not role:
            flash('All fields (name, email, role) are required!')
            return redirect(url_for('manage_users'))

        # Validate role
        if role not in ['teacher', 'substitute']:
            flash('Invalid role specified!')
            return redirect(url_for('manage_users'))

        # Check for duplicate email
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('A user with this email already exists!')
            return redirect(url_for('manage_users'))

        try:
            # Fetch grade, subject, and school objects
            grade_objs = Grade.query.filter(Grade.id.in_(grade_ids)).all() if grade_ids else []
            subject_objs = Subject.query.filter(Subject.id.in_(subject_ids)).all() if subject_ids else []
            school_objs = School.query.filter(School.id.in_(school_ids)).all() if school_ids else []

            # Log the fetched objects for debugging
            logger.info(f"Fetched objects: grades={len(grade_objs)}, subjects={len(subject_objs)}, schools={len(school_objs)}")

            # Get the current user to get their organization_id
            current_user = get_logged_in_user()
            
            # Create the new user
            new_user = User(
                name=name,
                email=email,
                role=role,
                phone=phone,
                organization_id=current_user.organization_id if current_user else None,
                created_by=current_user.id if current_user else None
            )
            
            # Log the organization_id for debugging
            logger.info(f"Setting organization_id={current_user.organization_id if current_user else None} for new user")

            # Assign grades, subjects, and schools to the new user
            new_user.grades.extend(grade_objs)  # Add all selected grades
            new_user.subjects.extend(subject_objs)  # Add all selected subjects
            new_user.schools.extend(school_objs)  # Add all selected schools

            # Add and commit changes to the database
            db.session.add(new_user)
            db.session.commit()

            # Flash a success message
            flash(f'User {name} ({email}) added successfully!')
            logger.info(f"User {name} ({email}) added successfully with ID {new_user.id}")

            return redirect(url_for('manage_users'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error in add_user: {e}")
            flash('An error occurred while adding the user. Please try again.')
            return redirect(url_for('manage_users'))

    except Exception as e:
        logger.error(f"Unexpected error in add_user: {e}")
        flash('An unexpected error occurred. Please try again.')
        return redirect(url_for('manage_users'))


@app.route('/edit_user/<int:user_id>', methods=['POST'])
@limiter.limit("10 per minute")
def edit_user(user_id):
    # Import the shared schools check function
    from blueprints.utils.shared_schools_check import check_shared_schools_access
    
    # Check if the current user has permission to edit this user
    if not check_shared_schools_access(user_id):
        flash('You do not have permission to edit this user.')
        return redirect(url_for('manage_users'))
    
    # Fetch the user from the database
    user = User.query.get_or_404(user_id)

    # Update basic user details
    user.name = request.form['name']
    user.email = request.form['email']
    user.role = request.form['role']
    user.phone = request.form.get('phone', None)
    
    # Get multiple schools
    school_ids = request.form.getlist('schools')  # List of selected school IDs
    school_objs = School.query.filter(School.id.in_(school_ids)).all()

    # Update grades, subjects, and schools
    grade_ids = request.form.getlist('grades')  # List of selected grade IDs
    subject_ids = request.form.getlist('subjects')  # List of selected subject IDs
    grade_objs = Grade.query.filter(Grade.id.in_(grade_ids)).all()
    subject_objs = Subject.query.filter(Subject.id.in_(subject_ids)).all()

    user.grades = grade_objs
    user.subjects = subject_objs
    user.schools = school_objs  # Update schools relationship

    # Save changes to the database
    db.session.commit()

    flash(f"User '{user.name}' updated successfully!")
    # Redirect to manage_admins if the user is an admin, otherwise to manage_users
    if user.role == 'admin_l2':
        return redirect(url_for('manage_admins'))
    else:
        return redirect(url_for('manage_users'))


@app.route('/user_profile/<int:user_id>')
def user_profile(user_id):
    # Get the current logged-in user
    current_user = get_logged_in_user()
    if not current_user:
        flash('Please log in to continue.')
        return redirect(url_for('index'))
    
    # Import the shared schools check function
    from blueprints.utils.shared_schools_check import check_shared_schools_access
    
    # Check if the current user has permission to view this user's profile
    if current_user.role == 'admin_l2' and not check_shared_schools_access(user_id):
        flash('You do not have permission to view this user profile.')
        return redirect(url_for('manage_users'))
        
    # Query the database for the user by ID
    user = User.query.get(user_id)
    # Validate if the user exists
    if not user:
        return "User not found", 404

    requests = []

    # If user is a teacher, get all their submitted substitute requests
    if user.role == 'teacher':
        requests = SubstituteRequest.query.filter_by(teacher_id=user.id).order_by(SubstituteRequest.date.desc()).all()

    # If user is a substitute, get all their accepted substitute requests
    elif user.role == 'substitute':
        # Join with User to get teacher information
        requests = db.session.query(
            SubstituteRequest, User.name.label("teacher_name")
        ).join(User, SubstituteRequest.teacher_id == User.id).filter(
            SubstituteRequest.substitute_id == user.id
        ).order_by(SubstituteRequest.date.desc()).all()

    # Render the user profile page with appropriate data
    return render_template('user_profile.html', user=user, requests=requests, current_user=current_user)


@app.route('/edit_request/<int:request_id>', methods=['GET', 'POST'])
def edit_request(request_id):
    # Ensure user is authenticated
    logged_in_user = get_logged_in_user()
    if not logged_in_user:
        flash('Please log in to continue.')
        return redirect(url_for('index'))

    # Get the substitute request
    sub_request = SubstituteRequest.query.get_or_404(request_id)

    # Ensure the user is the teacher who created the request
    if sub_request.teacher_id != logged_in_user.id:
        flash('You can only edit your own substitute requests.')
        return redirect(url_for('dashboard'))

    # Ensure the request is still open
    if sub_request.status != 'Open':
        flash('You can only edit open substitute requests.')
        return redirect(url_for('dashboard'))

    if request.method == 'GET':
        # Format the date for the form
        formatted_date = sub_request.date.strftime('%m/%d/%Y')
        return render_template('request.html', sub_request=sub_request, formatted_date=formatted_date, edit_mode=True, user=logged_in_user)

    elif request.method == 'POST':
        try:
            # Get the date and time from the form
            date_str = request.form['date']
            time_str = request.form['time']
            
            # Validate that the date and time are in the future and not on a weekend
            from helpers import is_future_date_time
            if not is_future_date_time(date_str, time_str, logged_in_user):
                flash('Error: Substitute requests can only be created for future weekdays (Monday-Friday).')
                return redirect(url_for('edit_request', request_id=request_id))
            
            # Update the substitute request
            sub_request.date = datetime.strptime(date_str, '%m/%d/%Y')
            sub_request.time = time_str
            sub_request.details = request.form.get('details', '').strip()
            sub_request.reason = request.form.get('reason', '')
            sub_request.grade_id = request.form.get('grade_id')
            sub_request.subject_id = request.form.get('subject_id')

            # Save changes
            db.session.commit()

            flash('Substitute request updated successfully!')
        except Exception as e:
            flash('An error occurred while updating the request.')
            logger.error(f"Error: {e}")

        return redirect(url_for('dashboard'))


@app.route('/delete_request/<int:request_id>', methods=['POST'])
def delete_request(request_id):
    # Ensure user is authenticated
    logged_in_user = get_logged_in_user()
    if not logged_in_user:
        flash('Please log in to continue.')
        return redirect(url_for('index'))

    # Get the substitute request
    sub_request = SubstituteRequest.query.get_or_404(request_id)

    # Ensure the user is the teacher who created the request
    if sub_request.teacher_id != logged_in_user.id:
        flash('You can only delete your own substitute requests.')
        return redirect(url_for('dashboard'))

    # Ensure the request is still open
    if sub_request.status != 'Open':
        flash('You can only delete open substitute requests.')
        return redirect(url_for('dashboard'))

    try:
        # Delete the substitute request
        db.session.delete(sub_request)
        db.session.commit()

        flash('Substitute request deleted successfully!')
    except Exception as e:
        flash('An error occurred while deleting the request.')
        logger.error(f"Error: {e}")

    return redirect(url_for('dashboard'))


@app.route('/delete_user/<int:user_id>', methods=['POST'])
@limiter.limit("5 per minute")
def delete_user(user_id):
    # Ensure user is authenticated and has admin role
    if not is_authenticated(required_role='admin'):
        flash('Access denied. Admins only.')
        return redirect(url_for('index'))
    
    # Import the shared schools check function
    from blueprints.utils.shared_schools_check import check_shared_schools_access
    
    # Check if the current user has permission to delete this user
    logged_in_user = get_logged_in_user()
    if logged_in_user.role == 'admin_l2' and not check_shared_schools_access(user_id):
        flash('You do not have permission to delete this user.')
        return redirect(url_for('manage_users'))

    # Find the user to delete
    user = User.query.get_or_404(user_id)

    # Handle all substitute requests related to this user in a single query
    # This is more efficient than making separate queries
    all_requests = SubstituteRequest.query.filter(
        db.or_(
            SubstituteRequest.teacher_id == user.id,
            SubstituteRequest.substitute_id == user.id
        )
    ).all()

    for req in all_requests:
        if req.teacher_id == user.id:
            # If user is the teacher, delete the request
            db.session.delete(req)
        elif req.substitute_id == user.id:
            # If user is the substitute, just remove the assignment
            req.substitute_id = None
            req.status = 'Open'

    # Store the user's role before deletion
    user_role = user.role
    user_name = user.name
    
    # Delete the user
    db.session.delete(user)
    db.session.commit()

    flash(f"User '{user_name}' has been removed successfully.")
    # Redirect to manage_admins if the user was an admin, otherwise to manage_users
    if user_role == 'admin_l2':
        return redirect(url_for('manage_admins'))
    else:
        return redirect(url_for('manage_users'))


@app.route('/transfer_admin_ownership', methods=['POST'])
def transfer_admin_ownership():
    """Transfer level 1 admin ownership to another user."""
    # Ensure user is authenticated and has level 1 admin role
    if not is_authenticated(required_role='admin_l1'):
        flash('Access denied. Only level 1 admins can transfer ownership.')
        return redirect(url_for('admin_dashboard'))
    
    # Get the current admin
    current_admin = get_logged_in_user()
    
    # Get form data
    new_admin_email = request.form.get('new_admin_email')
    confirmation = request.form.get('confirmation')
    
    # Validate inputs
    if not new_admin_email:
        flash('Email address is required!')
        return redirect(url_for('admin_dashboard'))
    
    if confirmation != 'confirm':
        flash('You must confirm the transfer by typing "confirm"!')
        return redirect(url_for('admin_dashboard'))
    
    # Check if the new admin email is the same as the current admin
    if new_admin_email == current_admin.email:
        flash('You cannot transfer ownership to yourself!')
        return redirect(url_for('admin_dashboard'))
    
    # Check if the new admin already exists
    new_admin = User.query.filter_by(email=new_admin_email).first()
    
    if new_admin:
        # If the user already exists, update their role to admin_l1
        # Save their previous role in case we need to revert
        previous_role = new_admin.role
        
        # If the user is already an admin_l1, don't allow the transfer
        if previous_role == 'admin_l1':
            flash('This user is already a level 1 admin!')
            return redirect(url_for('admin_dashboard'))
        
        # Update the user's role to admin_l1
        new_admin.role = 'admin_l1'
        
        # If the user was a teacher or substitute, remove their grade and subject associations
        if previous_role in ['teacher', 'substitute']:
            # Clear grade and subject associations
            new_admin.grades = []
            new_admin.subjects = []
    else:
        # Create a new user with admin_l1 role
        new_admin = User(
            email=new_admin_email,
            name=new_admin_email.split('@')[0],  # Use part of email as name
            role='admin_l1',
            created_by=current_admin.id
        )
        db.session.add(new_admin)
    
    # Change the current admin's role to admin_l2
    current_admin.role = 'admin_l2'
    
    # Commit changes to the database
    db.session.commit()
    
    # Update session to reflect the role change
    session['user_info'] = {'email': current_admin.email, 'role': 'admin_l2'}
    
    # Flash a success message
    flash(f'Admin ownership transferred to {new_admin_email} successfully! You are now a level 2 admin.')
    
    # Redirect to logout since the user's role has changed
    return redirect(url_for('logout'))


# Run the application if this file is executed directly
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

@app.route('/manage_schools', methods=['GET', 'POST'])
def manage_schools():
    """Manage schools (for level 1 admins only)."""
    # Ensure user is authenticated and is a level 1 admin
    if not is_authenticated(required_role='admin_l1'):
        flash('Access denied. Only level 1 admins can manage schools.')
        return redirect(url_for('index'))
    
    # Get the logged-in user
    logged_in_user = get_logged_in_user()
    
    # Handle form submission for adding a new school
    if request.method == 'POST':
        school_name = request.form.get('school_name')
        school_code = request.form.get('school_code')
        
        # Validate inputs
        if not school_name or not school_code:
            flash('School name and code are required.')
            return redirect(url_for('manage_schools'))
        
        try:
            # Check if school with this name or code already exists
            existing_school = School.query.filter(
                (School.name == school_name) | (School.code == school_code)
            ).first()
            
            if existing_school:
                if existing_school.name == school_name:
                    flash(f'A school with the name "{school_name}" already exists.')
                else:
                    flash(f'A school with the code "{school_code}" already exists.')
                return redirect(url_for('manage_schools'))
            
            # Create new school
            new_school = School(
                name=school_name,
                code=school_code,
                level1_admin_id=logged_in_user.id  # Associate with the current level 1 admin
            )
            
            db.session.add(new_school)
            db.session.commit()
            
            flash(f'School "{school_name}" added successfully.')
            return redirect(url_for('manage_schools'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}')
            return redirect(url_for('manage_schools'))
    
    # Get all schools for display
    schools = School.query.all()
    
    return render_template(
        'manage_schools.html',
        user=logged_in_user,
        schools=schools
    )
@app.route('/edit_school/<int:school_id>', methods=['POST'])
def edit_school(school_id):
    """Edit an existing school."""
    # Ensure user is authenticated and is a level 1 admin
    if not is_authenticated(required_role='admin_l1'):
        flash('Access denied. Only level 1 admins can manage schools.')
        return redirect(url_for('index'))
    
    # Get the school to edit
    school = School.query.get_or_404(school_id)
    
    # Get form data
    school_name = request.form.get('school_name')
    school_code = request.form.get('school_code')
    
    # Validate inputs
    if not school_name or not school_code:
        flash('School name and code are required.')
        return redirect(url_for('manage_schools'))
    
    try:
        # Check if another school with this name or code already exists
        existing_school = School.query.filter(
            (School.name == school_name) | (School.code == school_code),
            School.id != school_id
        ).first()
        
        if existing_school:
            if existing_school.name == school_name:
                flash(f'Another school with the name "{school_name}" already exists.')
            else:
                flash(f'Another school with the code "{school_code}" already exists.')
            return redirect(url_for('manage_schools'))
        
        # Update school
        school.name = school_name
        school.code = school_code
        
        db.session.commit()
        
        flash(f'School "{school_name}" updated successfully.')
        return redirect(url_for('manage_schools'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred: {str(e)}')
        return redirect(url_for('manage_schools'))

@app.route('/delete_school/<int:school_id>', methods=['POST'])
def delete_school(school_id):
    """Delete a school."""
    # Ensure user is authenticated and is a level 1 admin
    if not is_authenticated(required_role='admin_l1'):
        flash('Access denied. Only level 1 admins can manage schools.')
        return redirect(url_for('index'))
    
    # Get the school to delete
    school = School.query.get_or_404(school_id)
    
    try:
        # Check if there are users associated with this school
        users_count = len(school.associated_users)
        if users_count > 0:
            flash(f'Cannot delete school "{school.name}" because it has {users_count} users associated with it. Reassign these users to another school first.')
            return redirect(url_for('manage_schools'))
        
        # Check if there are substitute requests associated with this school
        # We still need to check SubstituteRequest.school_id since it's not a legacy field
        requests_count = SubstituteRequest.query.filter_by(school_id=school_id).count()
        if requests_count > 0:
            flash(f'Cannot delete school "{school.name}" because it has {requests_count} substitute requests associated with it.')
            return redirect(url_for('manage_schools'))
        
        # Delete the school
        db.session.delete(school)
        db.session.commit()
        
        flash(f'School "{school.name}" deleted successfully.')
        return redirect(url_for('manage_schools'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred: {str(e)}')
        return redirect(url_for('manage_schools'))