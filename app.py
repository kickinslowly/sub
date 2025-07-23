from flask import Flask, redirect, url_for, session, render_template, request, flash, jsonify
from authlib.integrations.flask_client import OAuth
from config import Config
from datetime import datetime, timedelta
from models import User, SubstituteRequest, Grade, Subject, School, user_grades, user_subjects # Import models
from sqlalchemy.orm import aliased
import uuid
import sqlite3
import os
import sqlalchemy.exc  # Import SQLAlchemy exceptions
from werkzeug.security import check_password_hash
from twilio.rest import Client
from helpers import requires_role, is_tech_coordinator, is_admin_l2, is_admin, register_template_filters

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
from extensions import db, mail
db.init_app(app)
mail.init_app(app)

# Register custom template filters
register_template_filters(app)

# Initialize database migrations
from migrations import init_migrations
init_migrations(app)
oauth = OAuth(app)

# Initialize database backup scheduler
from scheduler import start_scheduler, create_immediate_backup
from backup import get_backup_info, ensure_backup_dir

# Ensure backup directory exists
with app.app_context():
    ensure_backup_dir()
    
    # Create initial backups if they don't exist
    backup_info = get_backup_info()
    if not backup_info['daily_backup']['exists']:
        create_immediate_backup('daily')
    if not backup_info['weekly_backup']['exists']:
        create_immediate_backup('weekly')
    
    # Start the scheduler
    start_scheduler()

# Initialize Twilio client
if hasattr(Config, 'TWILIO_ACCOUNT_SID') and hasattr(Config, 'TWILIO_AUTH_TOKEN'):
    if Config.TWILIO_ACCOUNT_SID and Config.TWILIO_AUTH_TOKEN and Config.TWILIO_PHONE_NUMBER:
        # Use the init_twilio function from extensions.py
        from extensions import init_twilio
        if init_twilio(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN):
            print("Twilio client initialized successfully")
        else:
            print("Failed to initialize Twilio client")
            print("SMS functionality will be disabled")
    else:
        print("Twilio credentials are not properly configured. SMS functionality will be disabled.")
else:
    print("Twilio configuration is missing. SMS functionality will be disabled.")

# Import helper functions after Twilio client is initialized
from helpers import send_email, send_sms

print("Registering models...")
# Wrap database queries in app.app_context() to ensure they work
with app.app_context():
    # Create all tables first
    db.create_all()
    print("Created all database tables")

    print("Registered tables in metadata:", db.metadata.tables.keys())
    try:
        print("Grades:", Grade.query.all())
    except Exception as e:
        print(f"Error querying Grades table: {e}")
        # If there's an error, try to create the tables again
        db.create_all()
        print("Attempted to create tables again after error")

def seed_database():
    """
    Seed the database with initial values for grades and subjects
    if they don't already exist.
    """
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

    # Commit changes only if we have added new data
    db.session.commit()


# Function to check and add missing columns
def update_database_schema():
    """Check if required columns exist in tables and handle schema migrations."""
    try:
        # Get the database path from the app config
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']

        # Handle both relative and absolute paths
        if db_uri.startswith('sqlite:///'):
            # Relative path
            db_path = db_uri.replace('sqlite:///', '')
            # Make it absolute if it's not already
            if not os.path.isabs(db_path):
                # In Flask, relative database paths are relative to the instance directory
                # Use Flask's instance_path attribute
                db_path = os.path.join(app.instance_path, db_path)
        elif db_uri.startswith('sqlite:////'):
            # Absolute path
            db_path = db_uri.replace('sqlite:////', '')
        else:
            print(f"Unsupported database URI format: {db_uri}")
            return

        print(f"Using database path: {db_path}")

        # Connect to the SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if the substitute_request table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='substitute_request'")
        if cursor.fetchone() is None:
            # Table doesn't exist yet, it will be created by db.create_all()
            print("substitute_request table doesn't exist yet, it will be created by db.create_all()")
        else:
            # Check which columns exist in the substitute_request table
            cursor.execute("PRAGMA table_info(substitute_request)")
            columns_info = cursor.fetchall()
            columns = [column[1] for column in columns_info]
            print(f"Existing columns in substitute_request: {columns}")

            # Check if all required columns exist
            required_columns = ['id', 'teacher_id', 'date', 'time', 'details', 'reason', 'status', 'substitute_id', 'token', 'created_at', 'grade_id', 'subject_id']
            missing_columns = [col for col in required_columns if col not in columns]

            if missing_columns:
                print(f"Missing columns in substitute_request table: {missing_columns}")

                # If 'reason' column is missing, try to add it
                if 'reason' in missing_columns:
                    try:
                        print("Adding reason column...")
                        cursor.execute("ALTER TABLE substitute_request ADD COLUMN reason VARCHAR(20)")
                        conn.commit()
                        print("Added reason column to substitute_request table")
                        missing_columns.remove('reason')
                    except sqlite3.OperationalError as e:
                        print(f"Error adding reason column: {e}")

                # If 'created_at' column is missing, try to add it
                if 'created_at' in missing_columns:
                    try:
                        print("Adding created_at column...")
                        cursor.execute("ALTER TABLE substitute_request ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                        current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                        cursor.execute(f"UPDATE substitute_request SET created_at = '{current_time}'")
                        conn.commit()
                        print("Added created_at column to substitute_request table")
                        missing_columns.remove('created_at')
                    except sqlite3.OperationalError as e:
                        print(f"Error adding created_at column: {e}")

                # If 'grade_id' column is missing, try to add it
                if 'grade_id' in missing_columns:
                    try:
                        print("Adding grade_id column...")
                        cursor.execute("ALTER TABLE substitute_request ADD COLUMN grade_id INTEGER")
                        conn.commit()
                        print("Added grade_id column to substitute_request table")
                        missing_columns.remove('grade_id')
                    except sqlite3.OperationalError as e:
                        print(f"Error adding grade_id column: {e}")

                # If 'subject_id' column is missing, try to add it
                if 'subject_id' in missing_columns:
                    try:
                        print("Adding subject_id column...")
                        cursor.execute("ALTER TABLE substitute_request ADD COLUMN subject_id INTEGER")
                        conn.commit()
                        print("Added subject_id column to substitute_request table")
                        missing_columns.remove('subject_id')
                    except sqlite3.OperationalError as e:
                        print(f"Error adding subject_id column: {e}")

                # If there are still missing columns that couldn't be added, drop and recreate the table
                if missing_columns:
                    print(f"Still missing columns: {missing_columns}. Will drop and recreate the table.")

                    # Backup existing data
                    cursor.execute("CREATE TABLE IF NOT EXISTS substitute_request_backup AS SELECT * FROM substitute_request")

                    # Drop the table
                    cursor.execute("DROP TABLE substitute_request")

                    conn.commit()
                    print("Dropped substitute_request table. It will be recreated by db.create_all()")
            else:
                print("All required columns exist in substitute_request table")

        # Check if the school table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='school'")
        if cursor.fetchone() is None:
            # Table doesn't exist yet, it will be created by db.create_all()
            print("school table doesn't exist yet, it will be created by db.create_all()")
        else:
            # Check which columns exist in the school table
            cursor.execute("PRAGMA table_info(school)")
            columns_info = cursor.fetchall()
            columns = [column[1] for column in columns_info]
            print(f"Existing columns in school: {columns}")

            # Check if all required columns exist
            required_columns = ['id', 'name', 'code', 'level1_admin_id']
            missing_columns = [col for col in required_columns if col not in columns]

            if missing_columns:
                print(f"Missing columns in school table: {missing_columns}")

                # If 'level1_admin_id' column is missing, try to add it
                if 'level1_admin_id' in missing_columns:
                    try:
                        print("Adding level1_admin_id column...")
                        cursor.execute("ALTER TABLE school ADD COLUMN level1_admin_id INTEGER")
                        conn.commit()
                        print("Added level1_admin_id column to school table")
                        missing_columns.remove('level1_admin_id')
                    except sqlite3.OperationalError as e:
                        print(f"Error adding level1_admin_id column: {e}")

                # If there are still missing columns that couldn't be added, drop and recreate the table
                if missing_columns:
                    print(f"Still missing columns: {missing_columns}. Will drop and recreate the table.")

                    # Backup existing data
                    cursor.execute("CREATE TABLE IF NOT EXISTS school_backup AS SELECT * FROM school")

                    # Drop the table
                    cursor.execute("DROP TABLE school")

                    conn.commit()
                    print("Dropped school table. It will be recreated by db.create_all()")
            else:
                print("All required columns exist in school table")

        # SCHEMA MIGRATION: Handle the transition from campus field to school_id
        
        # First, ensure all tables exist by calling db.create_all()
        conn.close()
        with app.app_context():
            db.create_all()
        
        # Reconnect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the user table has the campus column
        cursor.execute("PRAGMA table_info(user)")
        columns_info = cursor.fetchall()
        columns = [column[1] for column in columns_info]
        
        if 'campus' in columns:
            print("Found campus column in user table")
            
            # Check if the user table has the school_id column
            if 'school_id' not in columns:
                try:
                    print("Adding school_id column to user table...")
                    cursor.execute("ALTER TABLE user ADD COLUMN school_id INTEGER")
                    conn.commit()
                    print("Added school_id column to user table")
                except sqlite3.OperationalError as e:
                    print(f"Error adding school_id column: {e}")
                    conn.close()
                    return
            
            # Get all unique campus values from the user table
            cursor.execute("SELECT DISTINCT campus FROM user WHERE campus IS NOT NULL AND campus != ''")
            unique_campuses = cursor.fetchall()
            
            if unique_campuses:
                print(f"Found {len(unique_campuses)} unique campus values")
                
                # Create a mapping of campus codes to school names
                campus_to_name = {
                    'AUES': 'AUES Elementary School',
                    'PAHS': 'PAHS High School',
                    'SCHS': 'SCHS High School',
                    'PCC': 'PCC School',
                    'MAINTENANCE': 'Maintenance Department',
                    'CAFETERIA': 'Cafeteria Department',
                    'TRANSPORTATION': 'Transportation Department',
                    'DO': 'District Office'
                }
                
                # Process each unique campus
                for (campus,) in unique_campuses:
                    if campus:
                        campus_code = campus.strip().upper()
                        school_name = campus_to_name.get(campus_code, f"{campus_code} School")
                        
                        # Check if this school already exists in the database
                        cursor.execute("SELECT id FROM school WHERE code = ?", (campus_code,))
                        existing_school = cursor.fetchone()
                        
                        if existing_school:
                            school_id = existing_school[0]
                            print(f"School {campus_code} already exists with ID {school_id}")
                        else:
                            # Insert the new school
                            cursor.execute("INSERT INTO school (name, code) VALUES (?, ?)", (school_name, campus_code))
                            conn.commit()
                            
                            # Get the ID of the newly inserted school
                            cursor.execute("SELECT id FROM school WHERE code = ?", (campus_code,))
                            school_id = cursor.fetchone()[0]
                            print(f"Created new school {campus_code} with ID {school_id}")
                        
                        # Update users with this campus to use the new school_id
                        cursor.execute("UPDATE user SET school_id = ? WHERE campus = ?", (school_id, campus))
                        conn.commit()
                        print(f"Updated users with campus {campus} to use school_id {school_id}")
                
                print("Migration from campus to school_id completed successfully")
            else:
                print("No unique campus values found, no migration needed")
        else:
            print("Campus column not found in user table, no migration needed")
        
        conn.close()
    except Exception as e:
        print(f"Error updating database schema: {e}")
        import traceback
        traceback.print_exc()

# Initialize the database and ensure all tables and columns are created
with app.app_context():
    # First create all tables based on models
    db.create_all()
    print("All database tables created based on models")
    
    # Then update schema for any specific migrations
    update_database_schema()  # Update the database schema if needed
    
    # Finally seed the database with initial data
    seed_database()  # Seed the database with default data


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
        print(f"[Error] Database operational error in get_logged_in_user: {e}")
        flash("A database error occurred. Please contact the administrator.")
        return None
    except sqlalchemy.exc.SQLAlchemyError as e:
        # Handle other SQLAlchemy errors
        print(f"[Error] Database error in get_logged_in_user: {e}")
        flash("A database error occurred. Please contact the administrator.")
        return None
    except Exception as e:
        # Handle any other unexpected errors
        print(f"[Error] Unexpected error in get_logged_in_user: {e}")
        flash("An unexpected error occurred. Please contact the administrator.")
        return None


def is_authenticated(required_role=None):
    """Checks if a user is logged in and matches the required role if specified."""
    user_info = session.get('user_info')
    if not user_info:
        return False
        
    # If no specific role is required, any authenticated user is allowed
    if not required_role:
        return True
        
    user_role = user_info.get('role')
    
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
    else:
        # For other roles, exact match is required
        return user_role == required_role


# Routes
@app.route('/')
def index():
    return render_template('login.html')


@app.route('/login')
def login():
    redirect_uri = url_for('authorized', _external=True)
    return google.authorize_redirect(redirect_uri)




@app.route('/logout')
def logout():
    session.clear()
    flash('You have successfully logged out.')
    return redirect(url_for('index'))


@app.route('/login/authorized')
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

            # If user doesn't exist, create a new user
            if not user:
                # Create new user with minimal required fields to avoid schema issues
                new_user = User(
                    email=user_info['email'],
                    name=user_info.get('name', 'Unknown'),
                    role=role
                )
                db.session.add(new_user)
                user = new_user
            else:
                # Update role if it's missing or if it's the old 'admin' role that needs to be migrated
                if not user.role or (user.role == 'admin' and role in ['admin_l1', 'admin_l2']):
                    user.role = role
                    print(f"[Debug] Updated user role from 'admin' to '{role}'")

            db.session.commit()
        except sqlalchemy.exc.OperationalError as e:
            # Handle database operational errors (like missing columns)
            print(f"[Error] Database operational error during user creation/update: {e}")
            flash("A database error occurred during login. Please contact the administrator.")
            db.session.rollback()
            return redirect(url_for('index'))
        except sqlalchemy.exc.SQLAlchemyError as e:
            # Handle other SQLAlchemy errors
            print(f"[Error] Database error during user creation/update: {e}")
            flash("A database error occurred during login. Please contact the administrator.")
            db.session.rollback()
            return redirect(url_for('index'))

        # Store user information in the session
        session['user_info'] = {'email': user.email, 'role': user.role}

        print(f"[Debug] Role Assigned: {user.role}, Email: {user.email}")

        # Redirect to the correct dashboard based on role
        if user.role in ['admin_l1', 'admin_l2']:
            return redirect(url_for('admin_dashboard'))
        elif user.role == 'substitute':
            return redirect(url_for('substitute_dashboard'))
        else:
            return redirect(url_for('dashboard'))

    except ValueError as e:
        flash('Invalid response from authentication server')
        print(f"[Error] OAuth value error: {e}")
        return redirect(url_for('index'))
    except KeyError as e:
        flash('Missing information in authentication response')
        print(f"[Error] Missing key in OAuth response: {e}")
        return redirect(url_for('index'))
    except sqlalchemy.exc.SQLAlchemyError as e:
        flash('Database error during login')
        print(f"[Error] Database error: {e}")
        return redirect(url_for('index'))
    except Exception as e:
        flash('Error during login')
        print(f"[Error] Login failed: {e}, User Info: {session.get('user_info', {})}")
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

    return render_template('substitute_dashboard.html', 
                          user=logged_in_user, 
                          accepted_requests=accepted_requests,
                          matching_requests=matching_requests)


@app.route('/edit_profile/<int:user_id>', methods=['GET', 'POST'])
def edit_profile(user_id):
    # Ensure user is authenticated
    logged_in_user = get_logged_in_user()
    if not logged_in_user:
        flash('Please log in to continue.')
        return redirect(url_for('index'))

    # Get the user to edit
    user_to_edit = User.query.get_or_404(user_id)
    
    # Check permissions: user can edit their own profile or admin_l2 can edit any profile
    if logged_in_user.id != user_to_edit.id and logged_in_user.role != 'admin_l2':
        flash('You do not have permission to edit this profile.')
        return redirect(url_for('user_profile', user_id=user_id))

    # Ensure user is a teacher, substitute, or admin_l2
    if logged_in_user.role not in ['teacher', 'substitute', 'admin_l2']:
        flash('This feature is only available for teachers, substitutes, and level 2 admins.')
        return redirect(url_for('dashboard'))

    # Fetch all grades, subjects, and schools for the form
    grades = Grade.query.order_by(Grade.id.asc()).all()
    subjects = Subject.query.order_by(Subject.id.asc()).all()
    schools = School.query.order_by(School.name.asc()).all()

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
        SubstituteRequest.query
        .filter_by(teacher_id=logged_in_user.id)
        .order_by(SubstituteRequest.date.desc())
        .all()
    )
    
    # Calculate total hours out
    from helpers import calculate_total_hours_out
    total_hours_out = calculate_total_hours_out(past_bookings)
    
    return render_template('dashboard.html', user=logged_in_user, past_bookings=past_bookings, total_hours_out=total_hours_out)


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
        cutoff_date = datetime.utcnow() - timedelta(days=15)
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
        
    # Get all teachers for the dropdown
    teachers = User.query.filter_by(role='teacher').order_by(User.name).all()
    
    return render_template('admin_request.html', teachers=teachers)


@app.route('/admin_create_request', methods=['POST'])
@requires_role('admin')
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
        
        # Validate that the date and time are in the future
        from helpers import is_future_date_time
        if not is_future_date_time(date, time):
            flash('Error: Substitute requests can only be created for future dates and times.')
            return redirect(url_for('admin_request_form'))

        # Validate teacher exists
        teacher = User.query.filter_by(id=teacher_id, role='teacher').first()
        if not teacher:
            flash('Invalid teacher selected.')
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
        sub_request = SubstituteRequest(
            teacher_id=teacher_id,
            date=datetime.strptime(date, '%m/%d/%Y'),
            time=time,
            details=details.strip(),
            reason=reason,
            grade_id=grade_id,
            subject_id=subject_id,
            school_id=teacher_school_id,
            token=token
        )
        db.session.add(sub_request)
        db.session.commit()

        # Generate dynamic link
        request_link = url_for('view_sub_request', token=token, _external=True)

        # Use the helper function to filter eligible substitutes at the database level
        from helpers import filter_eligible_substitutes
        eligible_substitutes = filter_eligible_substitutes(teacher)

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

        # Send notification with link to eligible substitutes
        subject = "New Substitute Request Available"

        for substitute in eligible_substitutes:
            email_body = f"""A new substitute request has been posted:
            📅 Date: {date}
            ⏰ Time: {time}
            👨‍🏫 Teacher: {teacher.name}
            📚 Grade: {grade_name}
            📖 Subject: {subject_name}
            📌 Details: {details or 'No additional details provided'}
            👉 Accept the request here: {request_link}"""
            send_email(subject, substitute.email, email_body)

            # Send SMS to eligible substitutes with phones
            if substitute.phone:
                sms_body = f"New sub request: Teacher {teacher.name}, Date {date}, Time {time}, Grade {grade_name}, Subject {subject_name}. Accept at: {request_link}"
                send_sms(substitute.phone, sms_body)

        # Send notification to admin via email
        admin_subject = "New Substitute Request Created"
        admin_email_body = f"""A new substitute request has been created:
        👨‍🏫 Teacher: {teacher.name}
        📅 Date: {date}
        ⏰ Time: {time}
        📚 Grade: {grade_name}
        📖 Subject: {subject_name}
        📌 Details: {details or 'No additional details provided'}"""
        # Send to admins in Config.ADMIN_EMAILS (for backward compatibility)
        for admin_email in Config.ADMIN_EMAILS:
            send_email(admin_subject, admin_email, admin_email_body)
            
        # Send to all level 2 admins
        level2_admins = User.query.filter_by(role='admin_l2').all()
        for admin in level2_admins:
            send_email(admin_subject, admin.email, admin_email_body)

        # Send SMS notification to admin
        admin_sms_body = f"New sub request: Teacher {teacher.name}, Date {date}, Time {time}, Grade {grade_name}, Subject {subject_name}, Reason {reason or 'Not specified'}"
        if hasattr(Config, 'ADMIN_PHONE_NUMBERS'):
            for admin_phone in Config.ADMIN_PHONE_NUMBERS:
                send_sms(admin_phone, admin_sms_body)

        # Send email notification to teacher
        teacher_subject = "Your Substitute Request Has Been Created"
        teacher_email_body = f"""A substitute request has been created for you:
        📅 Date: {date}
        ⏰ Time: {time}
        📚 Grade: {grade_name}
        📖 Subject: {subject_name}
        🔍 Reason: {reason or 'Not specified'}
        📌 Details: {details or 'No additional details provided'}
        You will be notified when a substitute accepts this request."""
        if teacher.email:
            send_email(teacher_subject, teacher.email, teacher_email_body)

        # Send SMS confirmation to teacher
        if teacher.phone:
            teacher_sms_body = f"Sub Request created for {date}, {time}. You will be notified when a substitute accepts."
            send_sms(teacher.phone, teacher_sms_body)

        flash('Substitute request created successfully! Notification sent to matching substitutes.')

    except Exception as e:
        flash('An error occurred while creating the request.')
        print(f"Error: {e}")

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

            # Validate that the date and time are in the future
            from helpers import is_future_date_time
            if not is_future_date_time(date, time):
                flash('Error: Substitute requests can only be created for future dates and times.')
                return redirect(url_for('request_form_and_submit'))

            teacher = get_logged_in_user()

            if teacher:
                token = str(uuid.uuid4())  # Generate unique token

                # Get grade and subject IDs from the form or auto-select if teacher has only one
                grade_id = request.form.get('grade_id')
                subject_id = request.form.get('subject_id')
                
                # If grade_id is not provided and teacher has exactly one grade, use that grade
                if not grade_id and len(teacher.grades) == 1:
                    grade_id = teacher.grades[0].id
                
                # If subject_id is not provided and teacher has exactly one subject, use that subject
                if not subject_id and len(teacher.subjects) == 1:
                    subject_id = teacher.subjects[0].id

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
                        token=token
                    )
                    db.session.add(sub_request)
                    db.session.commit()
                except ValueError as e:
                    flash('Invalid date format. Please use MM/DD/YYYY format.')
                    print(f"Date parsing error: {e}")
                    return redirect(url_for('request_form_and_submit'))
                except sqlalchemy.exc.SQLAlchemyError as e:
                    flash('Database error while saving request.')
                    print(f"Database error: {e}")
                    return redirect(url_for('dashboard'))

                # **Generate dynamic link**
                request_link = url_for('view_sub_request', token=token, _external=True)

                # Use the helper function to filter eligible substitutes at the database level
                from helpers import filter_eligible_substitutes
                eligible_substitutes = filter_eligible_substitutes(teacher)

                # **Send notification with link to eligible substitutes**
                subject = "New Substitute Request Available"

                notification_errors = []
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
                    email_body = f"""A new substitute request has been posted:
                    📅 Date: {date}
                    ⏰ Time: {time}
                    📚 Grade: {grade_name}
                    📖 Subject: {subject_name}
                    📌 Details: {details or 'No additional details provided'}
                    👉 Accept the request here: {request_link}"""
                    if not send_email(subject, substitute.email, email_body):
                        notification_errors.append(f"Failed to send email to {substitute.email}")

                # Send notification to admin via email
                admin_subject = "New Substitute Request Created"
                admin_email_body = f"""A new substitute request has been created:
                👨‍🏫 Teacher: {teacher.name}
                📅 Date: {date}
                ⏰ Time: {time}
                📚 Grade: {grade_name}
                📖 Subject: {subject_name}
                🔍 Reason: {reason or 'Not specified'}
                📌 Details: {details or 'No additional details provided'}"""
                # Send to admins in Config.ADMIN_EMAILS (for backward compatibility)
                for admin_email in Config.ADMIN_EMAILS:
                    if not send_email(admin_subject, admin_email, admin_email_body):
                        notification_errors.append(f"Failed to send email to admin {admin_email}")
                
                # Send to all level 2 admins
                level2_admins = User.query.filter_by(role='admin_l2').all()
                for admin in level2_admins:
                    if not send_email(admin_subject, admin.email, admin_email_body):
                        notification_errors.append(f"Failed to send email to admin {admin.email}")

                # Send SMS notification to admin
                admin_sms_body = f"New sub request: Teacher {teacher.name}, Date {date}, Time {time}, Grade {grade_name}, Subject {subject_name}, Reason {reason or 'Not specified'}"
                if hasattr(Config, 'ADMIN_PHONE_NUMBERS'):
                    for admin_phone in Config.ADMIN_PHONE_NUMBERS:
                        if not send_sms(admin_phone, admin_sms_body):
                            notification_errors.append(f"Failed to send SMS to admin {admin_phone}")

                # Send email notification to teacher
                teacher_subject = "Your Substitute Request Has Been Created"
                teacher_email_body = f"""A substitute request has been created:
                📅 Date: {date}
                ⏰ Time: {time}
                📚 Grade: {grade_name}
                📖 Subject: {subject_name}
                🔍 Reason: {reason or 'Not specified'}
                📌 Details: {details or 'No additional details provided'}
                You will be notified when a substitute accepts this request."""
                if teacher.email:
                    if not send_email(teacher_subject, teacher.email, teacher_email_body):
                        notification_errors.append(f"Failed to send email to teacher {teacher.email}")

                # Send SMS confirmation to teacher
                if teacher.phone:
                    teacher_sms_body = f"Sub Request created for {date}, {time}. You will be notified when a substitute accepts."
                    if not send_sms(teacher.phone, teacher_sms_body):
                        notification_errors.append(f"Failed to send SMS to teacher {teacher.phone}")

                if notification_errors:
                    print("Notification errors:", notification_errors)
                    flash('Substitute request submitted successfully, but some notifications failed to send.')
                else:
                    flash('Substitute request submitted successfully! Notification sent to matching substitutes.')
            else:
                flash('Error: Could not find your user account.')

        except KeyError as e:
            flash('Missing required field in form submission.')
            print(f"Form field error: {e}")
            return redirect(url_for('request_form_and_submit'))
        except Exception as e:
            flash('An error occurred while submitting the request.')
            print(f"Unexpected error: {e}")

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
        # Import helper functions for email templates
        from helpers import generate_admin_sub_filled_email, generate_teacher_sub_filled_email, generate_substitute_confirmation_email

        # 1. Email to admin
        admin_subject, admin_email_body = generate_admin_sub_filled_email(teacher, sub_request, logged_in_user)
        for admin_email in Config.ADMIN_EMAILS:
            send_email(admin_subject, admin_email, admin_email_body)

        # 2. Email to teacher
        teacher_subject, teacher_email_body = generate_teacher_sub_filled_email(sub_request, logged_in_user)
        send_email(teacher_subject, teacher.email, teacher_email_body)

        # 3. Email to substitute
        sub_subject, sub_email_body = generate_substitute_confirmation_email(teacher, sub_request)
        send_email(sub_subject, logged_in_user.email, sub_email_body)

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
    
    # Get all level 2 admins
    admins = User.query.filter_by(role='admin_l2').order_by(User.name).all()
    
    # Fetch all schools from the database
    schools = School.query.order_by(School.name.asc()).all()
    
    return render_template(
        'manage_admins.html',
        admins=admins,
        schools=schools,
        user=session['user_info']
    )


@app.route('/add_admin', methods=['POST'])
@requires_role('admin_l1')
def add_admin():
    """Route for tech coordinators to create level 2 admin accounts."""
    
    # Get form data
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    admin_type = request.form.get('admin_type', 'front_office')  # front_office or principal
    
    # Get selected schools
    school_ids = request.form.getlist('schools')  # List of selected school IDs
    school_objs = School.query.filter(School.id.in_(school_ids)).all()
    
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
        created_by=logged_in_user.id if logged_in_user else None
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
def manage_users():
    # Ensure user is authenticated
    if 'user_info' not in session:
        flash('Please log in to access this page.')
        return redirect(url_for('index'))

    # Get sort parameters from query string
    sort_by = request.args.get('sort_by', 'id')
    sort_order = request.args.get('sort_order', 'asc')

    # Base queries for teachers and substitutes
    teachers_query = User.query.filter_by(role='teacher')
    substitutes_query = User.query.filter_by(role='substitute')

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
    sub_request = SubstituteRequest.query.filter_by(token=token).first()

    if not sub_request:
        return jsonify({"status": "error", "message": "Invalid request"}), 404

    if sub_request.status != "Open":
        return jsonify({"status": "error", "message": "This position has already been filled"}), 400

    # Assign the logged-in user (substitute) to the request
    logged_in_user = get_logged_in_user()
    if not logged_in_user or logged_in_user.role != "substitute":
        return jsonify({"status": "error", "message": "Unauthorized action"}), 403

    sub_request.status = "Filled"
    sub_request.substitute_id = logged_in_user.id
    db.session.commit()

    # Fetch the teacher information
    teacher = User.query.get(sub_request.teacher_id)

    # Send email notifications
    # Import helper functions for email templates
    from helpers import generate_admin_sub_filled_email, generate_teacher_sub_filled_email, generate_substitute_confirmation_email

    # 1. Email to admin
    admin_subject, admin_email_body = generate_admin_sub_filled_email(teacher, sub_request, logged_in_user)
    for admin_email in Config.ADMIN_EMAILS:
        send_email(admin_subject, admin_email, admin_email_body)

    # 2. Email to teacher
    teacher_subject, teacher_email_body = generate_teacher_sub_filled_email(sub_request, logged_in_user)
    send_email(teacher_subject, teacher.email, teacher_email_body)

    # 3. Email to substitute
    sub_subject, sub_email_body = generate_substitute_confirmation_email(teacher, sub_request)
    send_email(sub_subject, logged_in_user.email, sub_email_body)

    # 4. Notify level 2 admins via email and SMS
    level2_admins = User.query.filter_by(role="admin_l2").all()
    
    # SMS notification is shorter due to character limitations
    admin_sms_body = f"Sub position filled: {teacher.name}, {sub_request.date.strftime('%B %d, %Y')}, {sub_request.time}, filled by {logged_in_user.name}"
    
    for admin in level2_admins:
        # Send email notification
        send_email(admin_subject, admin.email, admin_email_body)
        
        # Send SMS notification if phone number is available
        if admin.phone:
            send_sms(admin.phone, admin_sms_body)
    
    # Generate and fill absence report PDF
    try:
        from pdf_handler import generate_absence_form_data, fill_absence_form
        
        # Format the date for the PDF filename (YYYY-MM-DD)
        request_date = sub_request.date.strftime("%Y-%m-%d")
        
        # Generate form data from the request
        form_data = generate_absence_form_data(sub_request, teacher, logged_in_user)
        
        # Fill the PDF form
        pdf_path = fill_absence_form(teacher.name, request_date, form_data)
        
        print(f"Absence report PDF generated successfully: {pdf_path}")
    except Exception as e:
        print(f"Error generating absence report PDF: {e}")

    return jsonify({"status": "success", "message": "Position accepted!"})


@app.route('/add_user', methods=['POST'])
def add_user():
    # Get form data
    name = request.form.get('name')
    email = request.form.get('email')
    role = request.form.get('role')
    phone = request.form.get('phone')

    # Collect multiple grades, subjects, and schools from checkboxes
    grade_ids = request.form.getlist('grades')  # List of selected grade IDs
    subject_ids = request.form.getlist('subjects')  # List of selected subject IDs
    school_ids = request.form.getlist('schools')  # List of selected school IDs

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

    # Fetch grade, subject, and school objects
    grade_objs = Grade.query.filter(Grade.id.in_(grade_ids)).all()
    subject_objs = Subject.query.filter(Subject.id.in_(subject_ids)).all()
    school_objs = School.query.filter(School.id.in_(school_ids)).all()

    # Create the new user
    new_user = User(
        name=name,
        email=email,
        role=role,
        phone=phone
    )

    # Assign grades, subjects, and schools to the new user
    new_user.grades.extend(grade_objs)  # Add all selected grades
    new_user.subjects.extend(subject_objs)  # Add all selected subjects
    new_user.schools.extend(school_objs)  # Add all selected schools

    # Add and commit changes to the database
    db.session.add(new_user)
    db.session.commit()

    # Flash a success message
    flash(f'User {name} ({email}) added successfully!')

    return redirect(url_for('manage_users'))


@app.route('/edit_user/<int:user_id>', methods=['POST'])
def edit_user(user_id):
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
            # Update the substitute request
            sub_request.date = datetime.strptime(request.form['date'], '%m/%d/%Y')
            sub_request.time = request.form['time']
            sub_request.details = request.form.get('details', '').strip()
            sub_request.reason = request.form.get('reason', '')
            sub_request.grade_id = request.form.get('grade_id')
            sub_request.subject_id = request.form.get('subject_id')

            # Save changes
            db.session.commit()

            flash('Substitute request updated successfully!')
        except Exception as e:
            flash('An error occurred while updating the request.')
            print(f"Error: {e}")

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
        print(f"Error: {e}")

    return redirect(url_for('dashboard'))


@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    # Ensure user is authenticated and has admin role
    if not is_authenticated(required_role='admin'):
        flash('Access denied. Admins only.')
        return redirect(url_for('index'))

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