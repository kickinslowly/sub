from flask import Flask, redirect, url_for, session, render_template, request, flash, jsonify
from authlib.integrations.flask_client import OAuth
from config import Config
from datetime import datetime, timedelta
from models import User, SubstituteRequest, Grade, Subject, user_grades, user_subjects # Import models
import uuid
import sqlite3
import os
from werkzeug.security import check_password_hash
from twilio.rest import Client

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
from extensions import db, mail
db.init_app(app)
mail.init_app(app)
oauth = OAuth(app)

# Initialize Twilio client
twilio_initialized = False
if hasattr(Config, 'TWILIO_ACCOUNT_SID') and hasattr(Config, 'TWILIO_AUTH_TOKEN'):
    if Config.TWILIO_ACCOUNT_SID and Config.TWILIO_AUTH_TOKEN and Config.TWILIO_PHONE_NUMBER:
        try:
            # Update the global twilio_client in extensions.py
            import extensions
            extensions.twilio_client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
            # Set twilio_initialized to True without making an API call
            print("Twilio client initialized successfully")
            twilio_initialized = True
        except Exception as e:
            print(f"Failed to initialize Twilio client: {e}")
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
    print("Registered tables in metadata:", db.metadata.tables.keys())
    try:
        print("Grades:", Grade.query.all())
    except Exception as e:
        print(f"Error querying Grades table: {e}")

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
    """Check if required columns exist in substitute_request table and add them if not."""
    try:
        # Get the database path from the app config
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']

        # Handle both relative and absolute paths
        if db_uri.startswith('sqlite:///'):
            # Relative path
            db_path = db_uri.replace('sqlite:///', '')
            # Make it absolute if it's not already
            if not os.path.isabs(db_path):
                db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
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
            conn.close()
            return

        # Check which columns exist in the substitute_request table
        cursor.execute("PRAGMA table_info(substitute_request)")
        columns_info = cursor.fetchall()
        columns = [column[1] for column in columns_info]
        print(f"Existing columns in substitute_request: {columns}")

        # Check if all required columns exist
        required_columns = ['id', 'teacher_id', 'date', 'time', 'details', 'reason', 'status', 'substitute_id', 'token', 'created_at']
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

        conn.close()
    except Exception as e:
        print(f"Error updating database schema: {e}")
        import traceback
        traceback.print_exc()

# Add the seed function to the database initialization
with app.app_context():
    db.create_all()  # Create all necessary tables
    update_database_schema()  # Update the database schema if needed
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
    return User.query.filter_by(email=session['user_info']['email']).first()


def is_authenticated(required_role=None):
    """Checks if a user is logged in and matches the required role if specified."""
    user_info = session.get('user_info')
    if not user_info:
        return False
    if required_role and user_info.get('role') != required_role:
        return False
    return True


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

        # Look for existing user in the database
        user = User.query.filter_by(email=user_info['email']).first()

        # Determine user role
        role = 'admin' if user_info['email'] in app.config.get('ADMIN_EMAILS', []) else 'teacher'

        # If user doesn't exist, create a new user
        if not user:
            user = User(email=user_info['email'], name=user_info.get('name', 'Unknown'), role=role)
            db.session.add(user)
        else:
            # 🚨 Fix: Only update the role if the user is new, NOT if they already exist
            if not user.role:  # If role is missing (unlikely), assign one
                user.role = role

        db.session.commit()

        # Store user information in the session
        session['user_info'] = {'email': user.email, 'role': user.role}

        print(f"[Debug] Role Assigned: {user.role}, Email: {user.email}")

        # Redirect to the correct dashboard based on role
        return redirect(url_for('admin_dashboard' if user.role == 'admin' else (
            'substitute_dashboard' if user.role == 'substitute' else 'dashboard')))

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

    # Fetch all accepted requests and include teacher details
    accepted_requests = db.session.query(
        SubstituteRequest, User.name.label("teacher_name")
    ).join(User, SubstituteRequest.teacher_id == User.id).filter(
        SubstituteRequest.substitute_id == logged_in_user.id
    ).order_by(SubstituteRequest.date.desc()).all()

    # Fetch all open substitute requests
    open_requests_query = db.session.query(
        SubstituteRequest, User.name.label("teacher_name"), User
    ).join(User, SubstituteRequest.teacher_id == User.id).filter(
        SubstituteRequest.status == "Open"
    ).order_by(SubstituteRequest.date.asc())

    # Get all open requests
    all_open_requests = open_requests_query.all()

    # Filter requests based on substitute's preferences
    matching_requests = []

    for request, teacher_name, teacher in all_open_requests:
        # Check if the substitute has any grade preferences
        sub_has_grade_preferences = len(logged_in_user.grades) > 0

        # Check if the substitute has any subject preferences
        sub_has_subject_preferences = len(logged_in_user.subjects) > 0

        # If substitute has no preferences, show all requests
        if not sub_has_grade_preferences and not sub_has_subject_preferences:
            matching_requests.append((request, teacher_name, teacher))
            continue

        # Check for grade match
        grade_match = False
        if not sub_has_grade_preferences:
            # If substitute has no grade preferences, consider it a match
            grade_match = True
        else:
            # Get the set of grade IDs for the substitute and teacher
            sub_grade_ids = {grade.id for grade in logged_in_user.grades}
            teacher_grade_ids = {grade.id for grade in teacher.grades}

            # If there's any overlap or substitute has selected all grades, it's a match
            if not teacher_grade_ids or not sub_grade_ids or sub_grade_ids.intersection(teacher_grade_ids):
                grade_match = True

        # Check for subject match
        subject_match = False
        if not sub_has_subject_preferences:
            # If substitute has no subject preferences, consider it a match
            subject_match = True
        else:
            # Get the set of subject IDs for the substitute and teacher
            sub_subject_ids = {subject.id for subject in logged_in_user.subjects}
            teacher_subject_ids = {subject.id for subject in teacher.subjects}

            # If there's any overlap or substitute has selected all subjects, it's a match
            if not teacher_subject_ids or not sub_subject_ids or sub_subject_ids.intersection(teacher_subject_ids):
                subject_match = True

        # If both grade and subject match, add to matching requests
        if grade_match and subject_match:
            matching_requests.append((request, teacher_name, teacher))

    return render_template('substitute_dashboard.html', 
                          user=logged_in_user, 
                          accepted_requests=accepted_requests,
                          matching_requests=matching_requests)


@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    # Ensure user is authenticated
    logged_in_user = get_logged_in_user()
    if not logged_in_user:
        flash('Please log in to continue.')
        return redirect(url_for('index'))

    # Ensure user is a substitute
    if logged_in_user.role != 'substitute':
        flash('This feature is only available for substitute users.')
        return redirect(url_for('dashboard'))

    # Fetch all grades and subjects for the form
    grades = Grade.query.order_by(Grade.id.asc()).all()
    subjects = Subject.query.order_by(Subject.id.asc()).all()

    if request.method == 'POST':
        # Update user details
        logged_in_user.name = request.form['name']
        logged_in_user.email = request.form['email']
        logged_in_user.phone = request.form.get('phone', None)

        # Update grades and subjects
        grade_ids = request.form.getlist('grades')  # List of selected grade IDs
        subject_ids = request.form.getlist('subjects')  # List of selected subject IDs
        grade_objs = Grade.query.filter(Grade.id.in_(grade_ids)).all()
        subject_objs = Subject.query.filter(Subject.id.in_(subject_ids)).all()

        logged_in_user.grades = grade_objs
        logged_in_user.subjects = subject_objs

        # Save changes to the database
        db.session.commit()

        flash('Your profile has been updated successfully!')
        return redirect(url_for('substitute_dashboard'))

    return render_template('edit_profile.html', user=logged_in_user, grades=grades, subjects=subjects)


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
    return render_template('dashboard.html', user=logged_in_user, past_bookings=past_bookings)


@app.route('/api/teacher_bookings')
def api_teacher_bookings():
    """API endpoint to get teacher bookings for reactive dashboard."""
    logged_in_user = get_logged_in_user()
    if not logged_in_user:
        return jsonify({"error": "Not authenticated"}), 401

    # Get all bookings for the teacher
    bookings = SubstituteRequest.query.filter_by(teacher_id=logged_in_user.id).order_by(SubstituteRequest.date.desc()).all()

    # Convert bookings to JSON-serializable format
    bookings_data = []
    for booking in bookings:
        booking_data = {
            "id": booking.id,
            "date": booking.date.strftime('%Y-%m-%d'),
            "date_formatted": booking.date.strftime('%B %d, %Y'),
            "time": booking.time,
            "status": booking.status,
            "details": booking.details,
            "created_at": booking.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            "created_at_formatted": booking.created_at.strftime('%B %d, %Y at %I:%M %p'),
        }

        # Add substitute info if available
        if booking.status != "Open" and booking.substitute_user:
            booking_data["substitute"] = {
                "id": booking.substitute_user.id,
                "name": booking.substitute_user.name
            }

        bookings_data.append(booking_data)

    return jsonify({"bookings": bookings_data})


@app.route('/admin_dashboard', methods=['GET'])
def admin_dashboard():
    """Dashboard for admins."""
    # Ensure user is authenticated and has admin role
    if not is_authenticated(required_role='admin'):
        flash('Access denied. Admins only.')
        return redirect(url_for('index'))

    # Get all teachers for the create request form and display
    teachers = User.query.filter_by(role='teacher').order_by(User.name).all()

    # Get search parameters from request
    search_keyword = request.args.get('search_keyword', '')
    search_date = request.args.get('search_date', '')
    search_status = request.args.get('search_status', '')

    # Start with a base query
    query = SubstituteRequest.query

    # Apply filters based on search parameters
    if search_keyword:
        # Join with User table to search by teacher or substitute name
        teacher_ids = db.session.query(User.id).filter(
            User.name.ilike(f'%{search_keyword}%'),
            User.role == 'teacher'
        ).all()
        teacher_ids = [id[0] for id in teacher_ids]

        substitute_ids = db.session.query(User.id).filter(
            User.name.ilike(f'%{search_keyword}%'),
            User.role == 'substitute'
        ).all()
        substitute_ids = [id[0] for id in substitute_ids]

        # Filter by teacher or substitute name
        if teacher_ids and substitute_ids:
            query = query.filter(
                db.or_(
                    SubstituteRequest.teacher_id.in_(teacher_ids),
                    SubstituteRequest.substitute_id.in_(substitute_ids)
                )
            )
        elif teacher_ids:
            query = query.filter(SubstituteRequest.teacher_id.in_(teacher_ids))
        elif substitute_ids:
            query = query.filter(SubstituteRequest.substitute_id.in_(substitute_ids))
        else:
            # If no matching teachers or substitutes, return empty results
            query = query.filter(SubstituteRequest.id == -1)  # This will return no results

    # Filter by date if provided
    if search_date:
        try:
            search_date_obj = datetime.strptime(search_date, '%Y-%m-%d').date()
            query = query.filter(SubstituteRequest.date == search_date_obj)
        except ValueError:
            # If date format is invalid, ignore this filter
            pass

    # Filter by status if provided
    if search_status:
        query = query.filter(SubstituteRequest.status == search_status)

    # If no search parameters are provided, separate by recent/older
    if not (search_keyword or search_date or search_status):
        cutoff_date = datetime.utcnow() - timedelta(days=15)
        recent_requests = query.filter(
            SubstituteRequest.date >= cutoff_date
        ).order_by(SubstituteRequest.date.asc()).all()
        older_requests = query.filter(
            SubstituteRequest.date < cutoff_date
        ).order_by(SubstituteRequest.date.desc()).all()
    else:
        # If search parameters are provided, show all matching results as recent
        recent_requests = query.order_by(SubstituteRequest.date.desc()).all()
        older_requests = []

    return render_template(
        'admin_dashboard.html',
        user=session['user_info'],
        recent_requests=recent_requests,
        older_requests=older_requests,
        teachers=teachers,
        request=request  # Pass the request object to access args in the template
    )


@app.route('/admin_create_request', methods=['POST'])
def admin_create_request():
    """Handle admin creation of substitute requests."""
    # Ensure user is authenticated and has admin role
    if not is_authenticated(required_role='admin'):
        flash('Access denied. Admins only.')
        return redirect(url_for('index'))

    try:
        # Get form data
        teacher_id = request.form['teacher_id']
        date = request.form['date']
        time = request.form['time']
        details = request.form.get('details', '')
        reason = request.form.get('reason', '')

        # Validate teacher exists
        teacher = User.query.filter_by(id=teacher_id, role='teacher').first()
        if not teacher:
            flash('Invalid teacher selected.')
            return redirect(url_for('admin_dashboard'))

        # Generate unique token
        token = str(uuid.uuid4())

        # Create and save substitute request
        sub_request = SubstituteRequest(
            teacher_id=teacher_id,
            date=datetime.strptime(date, '%Y-%m-%d'),
            time=time,
            details=details.strip(),
            reason=reason,
            token=token
        )
        db.session.add(sub_request)
        db.session.commit()

        # Generate dynamic link
        request_link = url_for('view_sub_request', token=token, _external=True)

        # Get teacher's grades and subjects
        teacher_grades = [grade.id for grade in teacher.grades]
        teacher_subjects = [subject.id for subject in teacher.subjects]

        # Find eligible substitutes (matching grades and subjects)
        eligible_substitutes = []
        all_substitutes = User.query.filter_by(role='substitute').all()

        for substitute in all_substitutes:
            sub_grades = [grade.id for grade in substitute.grades]
            sub_subjects = [subject.id for subject in substitute.subjects]

            # Check if there's any overlap in grades and subjects
            if (set(teacher_grades) & set(sub_grades)) and (set(teacher_subjects) & set(sub_subjects)):
                eligible_substitutes.append(substitute)

        # If no eligible substitutes found, use all substitutes
        if not eligible_substitutes:
            eligible_substitutes = all_substitutes

        # Send notification with link to eligible substitutes
        subject = "New Substitute Request Available"

        for substitute in eligible_substitutes:
            email_body = f"""
            A new substitute request has been posted:

            📅 Date: {date}
            ⏰ Time: {time}
            👨‍🏫 Teacher: {teacher.name}
            📌 Details: {details or 'No additional details provided'}

            👉 Accept the request here: {request_link}
            """
            send_email(subject, substitute.email, email_body)

            # Send SMS to eligible substitutes with phones
            if substitute.phone:
                sms_body = f"New sub request: Teacher {teacher.name}, Date {date}, Time {time}. Accept at: {request_link}"
                send_sms(substitute.phone, sms_body)

        # Send notification to admin via email
        admin_subject = "New Substitute Request Created"
        admin_email_body = f"""
        A new substitute request has been created:

        👨‍🏫 Teacher: {teacher.name}
        📅 Date: {date}
        ⏰ Time: {time}
        📌 Details: {details or 'No additional details provided'}
        """
        for admin_email in Config.ADMIN_EMAILS:
            send_email(admin_subject, admin_email, admin_email_body)

        # Send SMS notification to admin
        admin_sms_body = f"New sub request: Teacher {teacher.name}, Date {date}, Time {time}, Reason {reason or 'Not specified'}"
        if hasattr(Config, 'ADMIN_PHONE_NUMBERS'):
            for admin_phone in Config.ADMIN_PHONE_NUMBERS:
                send_sms(admin_phone, admin_sms_body)

        # Send SMS confirmation to teacher
        if teacher.phone:
            teacher_sms_body = "Sub Request submitted successfully."
            send_sms(teacher.phone, teacher_sms_body)

        flash('Substitute request created successfully! Notification sent to all substitutes.')

    except Exception as e:
        flash('An error occurred while creating the request.')
        print(f"Error: {e}")

    return redirect(url_for('admin_dashboard'))


@app.route('/request', methods=['GET', 'POST'])
def request_form_and_submit():
    if request.method == 'GET':
        return render_template('request.html')

    elif request.method == 'POST':
        if 'user_info' not in session:
            return redirect(url_for('index'))

        try:
            date = request.form['date']
            time = request.form['time']
            details = request.form.get('details', '')
            reason = request.form.get('reason', '')

            teacher = get_logged_in_user()

            if teacher:
                token = str(uuid.uuid4())  # Generate unique token

                # Create and save substitute request
                sub_request = SubstituteRequest(
                    teacher_id=teacher.id,
                    date=datetime.strptime(date, '%Y-%m-%d'),
                    time=time,
                    details=details.strip(),
                    reason=reason,
                    token=token
                )
                db.session.add(sub_request)
                db.session.commit()

                # **Generate dynamic link**
                request_link = url_for('view_sub_request', token=token, _external=True)

                # **Send notification with link**
                substitutes = User.query.filter_by(role='substitute').all()
                subject = "New Substitute Request Available"

                for substitute in substitutes:
                    email_body = f"""
                    A new substitute request has been posted:

                    📅 Date: {date}
                    ⏰ Time: {time}
                    🔍 Reason: {reason or 'Not specified'}
                    📌 Details: {details or 'No additional details provided'}

                    👉 Accept the request here: {request_link}
                    """
                    send_email(subject, substitute.email, email_body)

                # Send notification to admin via email
                admin_subject = "New Substitute Request Created"
                admin_email_body = f"""
                A new substitute request has been created:

                👨‍🏫 Teacher: {teacher.name}
                📅 Date: {date}
                ⏰ Time: {time}
                🔍 Reason: {reason or 'Not specified'}
                📌 Details: {details or 'No additional details provided'}
                """
                for admin_email in Config.ADMIN_EMAILS:
                    send_email(admin_subject, admin_email, admin_email_body)

                # Send SMS notification to admin
                admin_sms_body = f"New sub request: Teacher {teacher.name}, Date {date}, Time {time}, Reason {reason or 'Not specified'}"
                if hasattr(Config, 'ADMIN_PHONE_NUMBERS'):
                    for admin_phone in Config.ADMIN_PHONE_NUMBERS:
                        send_sms(admin_phone, admin_sms_body)

                # Send SMS confirmation to teacher
                if teacher.phone:
                    teacher_sms_body = "Sub Request submitted successfully."
                    send_sms(teacher.phone, teacher_sms_body)

                flash('Substitute request submitted successfully! Notification sent.')
            else:
                flash('Error: Could not find your user account.')

        except Exception as e:
            flash('An error occurred while submitting the request.')
            print(f"Error: {e}")

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
        # 1. Email to admin
        admin_subject = "Substitute Request Filled"
        admin_email_body = f"""
        A substitute request has been filled:

        👨‍🏫 Teacher: {teacher.name}
        📅 Date: {sub_request.date.strftime('%Y-%m-%d')}
        ⏰ Time: {sub_request.time}
        🔍 Reason: {sub_request.reason or 'Not specified'}
        📌 Details: {sub_request.details or 'No additional details provided'}

        ✅ Filled by: {logged_in_user.name} ({logged_in_user.email})
        """
        for admin_email in Config.ADMIN_EMAILS:
            send_email(admin_subject, admin_email, admin_email_body)

        # 2. Email to teacher
        teacher_subject = "Your Substitute Request Has Been Filled"
        teacher_email_body = f"""
        Good news! Your substitute request has been filled:

        📅 Date: {sub_request.date.strftime('%Y-%m-%d')}
        ⏰ Time: {sub_request.time}
        🔍 Reason: {sub_request.reason or 'Not specified'}

        ✅ Filled by: {logged_in_user.name}
        📧 Contact: {logged_in_user.email}
        """
        send_email(teacher_subject, teacher.email, teacher_email_body)

        # 3. Email to substitute
        sub_subject = "Substitute Position Confirmation"
        sub_email_body = f"""
        Thank you for accepting the substitute position:

        👨‍🏫 Teacher: {teacher.name}
        📅 Date: {sub_request.date.strftime('%Y-%m-%d')}
        ⏰ Time: {sub_request.time}
        🔍 Reason: {sub_request.reason or 'Not specified'}
        📌 Details: {sub_request.details or 'No additional details provided'}

        ⚠️ Important: Please report to the front office at least 10 minutes before the scheduled time.
        """

        # Add grade and subject information if available
        if teacher.grades:
            grade_names = ", ".join([grade.name for grade in teacher.grades])
            sub_email_body += f"\n📚 Grade(s): {grade_names}"

        if teacher.subjects:
            subject_names = ", ".join([subject.name for subject in teacher.subjects])
            sub_email_body += f"\n📖 Subject(s): {subject_names}"

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


@app.route('/manage_users', methods=['GET'])
def manage_users():
    # Ensure user is authenticated
    if 'user_info' not in session:
        flash('Please log in to access this page.')
        return redirect(url_for('index'))

    # Fetch all teachers and substitutes from the database
    teachers = User.query.filter_by(role='teacher').order_by(User.id.asc()).all()
    substitutes = User.query.filter_by(role='substitute').order_by(User.id.asc()).all()

    # Fetch all grades and subjects from the database
    grades = Grade.query.order_by(Grade.id.asc()).all()
    subjects = Subject.query.order_by(Subject.id.asc()).all()

    # Render the template, passing the required data
    return render_template(
        'manage_users.html',
        teachers=teachers,
        substitutes=substitutes,
        grades=grades,
        subjects=subjects,
        user=session['user_info']
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
    # 1. Email to admin
    admin_subject = "Substitute Request Filled"
    admin_email_body = f"""
    A substitute request has been filled:

    👨‍🏫 Teacher: {teacher.name}
    📅 Date: {sub_request.date.strftime('%Y-%m-%d')}
    ⏰ Time: {sub_request.time}
    📌 Details: {sub_request.details or 'No additional details provided'}

    ✅ Filled by: {logged_in_user.name} ({logged_in_user.email})
    """
    for admin_email in Config.ADMIN_EMAILS:
        send_email(admin_subject, admin_email, admin_email_body)

    # 2. Email to teacher
    teacher_subject = "Your Substitute Request Has Been Filled"
    teacher_email_body = f"""
    Good news! Your substitute request has been filled:

    📅 Date: {sub_request.date.strftime('%Y-%m-%d')}
    ⏰ Time: {sub_request.time}

    ✅ Filled by: {logged_in_user.name}
    📧 Contact: {logged_in_user.email}
    """
    send_email(teacher_subject, teacher.email, teacher_email_body)

    # 3. Email to substitute
    sub_subject = "Substitute Position Confirmation"
    sub_email_body = f"""
    Thank you for accepting the substitute position:

    👨‍🏫 Teacher: {teacher.name}
    📅 Date: {sub_request.date.strftime('%Y-%m-%d')}
    ⏰ Time: {sub_request.time}
    📌 Details: {sub_request.details or 'No additional details provided'}

    ⚠️ Important: Please report to the front office at least 10 minutes before the scheduled time.
    """

    # Add grade and subject information if available
    if teacher.grades:
        grade_names = ", ".join([grade.name for grade in teacher.grades])
        sub_email_body += f"\n📚 Grade(s): {grade_names}"

    if teacher.subjects:
        subject_names = ", ".join([subject.name for subject in teacher.subjects])
        sub_email_body += f"\n📖 Subject(s): {subject_names}"

    send_email(sub_subject, logged_in_user.email, sub_email_body)

    return jsonify({"status": "success", "message": "Position accepted!"})


@app.route('/add_user', methods=['POST'])
def add_user():
    # Get form data
    name = request.form.get('name')
    email = request.form.get('email')
    role = request.form.get('role')
    phone = request.form.get('phone')

    # Collect multiple grades and subjects from checkboxes
    grade_ids = request.form.getlist('grades')  # List of selected grade IDs
    subject_ids = request.form.getlist('subjects')  # List of selected subject IDs

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

    # Fetch grade and subject objects
    grade_objs = Grade.query.filter(Grade.id.in_(grade_ids)).all()
    subject_objs = Subject.query.filter(Subject.id.in_(subject_ids)).all()

    # Create the new user
    new_user = User(
        name=name,
        email=email,
        role=role,
        phone=phone
    )

    # Assign grades and subjects to the new user
    new_user.grades.extend(grade_objs)  # Add all selected grades
    new_user.subjects.extend(subject_objs)  # Add all selected subjects

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

    # Update grades and subjects
    grade_ids = request.form.getlist('grades')  # List of selected grade IDs
    subject_ids = request.form.getlist('subjects')  # List of selected subject IDs
    grade_objs = Grade.query.filter(Grade.id.in_(grade_ids)).all()
    subject_objs = Subject.query.filter(Subject.id.in_(subject_ids)).all()

    user.grades = grade_objs
    user.subjects = subject_objs

    # Save changes to the database
    db.session.commit()

    flash(f"User '{user.name}' updated successfully!")
    return redirect(url_for('manage_users'))


@app.route('/user_profile/<int:user_id>')
def user_profile(user_id):
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
    return render_template('user_profile.html', user=user, requests=requests)


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
        formatted_date = sub_request.date.strftime('%Y-%m-%d')
        return render_template('request.html', sub_request=sub_request, formatted_date=formatted_date, edit_mode=True)

    elif request.method == 'POST':
        try:
            # Update the substitute request
            sub_request.date = datetime.strptime(request.form['date'], '%Y-%m-%d')
            sub_request.time = request.form['time']
            sub_request.details = request.form.get('details', '').strip()
            sub_request.reason = request.form.get('reason', '')

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

    # Handle substitute requests where this user is a teacher
    teacher_requests = SubstituteRequest.query.filter_by(teacher_id=user.id).all()
    for req in teacher_requests:
        db.session.delete(req)

    # Handle substitute requests where this user is a substitute
    substitute_requests = SubstituteRequest.query.filter_by(substitute_id=user.id).all()
    for req in substitute_requests:
        # Just remove the substitute assignment, don't delete the request
        req.substitute_id = None
        req.status = 'Open'

    # Delete the user
    db.session.delete(user)
    db.session.commit()

    flash(f"User '{user.name}' has been removed successfully.")
    return redirect(url_for('manage_users'))
