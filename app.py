from flask import Flask, redirect, url_for, session, render_template, request, flash, jsonify
from authlib.integrations.flask_client import OAuth
from config import Config
from datetime import datetime, timedelta
from helpers import send_email  # Import the send_email helper function
from extensions import db, mail  # Import the instances
from models import User, SubstituteRequest, Grade, Subject, user_grades, user_subjects # Import models
import uuid
import sqlite3
import os
from werkzeug.security import check_password_hash

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
mail.init_app(app)
oauth = OAuth(app)

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
    """Check if created_at column exists in substitute_request table and add it if not."""
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
            print("substitute_request table doesn't exist yet, skipping schema update")
            conn.close()
            return

        # Check if created_at column exists in the substitute_request table
        cursor.execute("PRAGMA table_info(substitute_request)")
        columns_info = cursor.fetchall()
        columns = [column[1] for column in columns_info]
        print(f"Existing columns in substitute_request: {columns}")

        if 'created_at' not in columns:
            print("created_at column not found, adding it now...")
            # Add the created_at column with a default value of current timestamp
            cursor.execute("ALTER TABLE substitute_request ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

            # Update existing records to have a created_at value
            current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(f"UPDATE substitute_request SET created_at = '{current_time}'")

            conn.commit()
            print("Added created_at column to substitute_request table and updated existing records")
        else:
            print("created_at column already exists in substitute_request table")

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

    return render_template('substitute_dashboard.html', user=logged_in_user, accepted_requests=accepted_requests)


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
    return render_template('dashboard.html', user=session['user_info'], past_bookings=past_bookings)


@app.route('/admin_dashboard', methods=['GET'])
def admin_dashboard():
    """Dashboard for admins."""
    # Ensure user is authenticated and has admin role
    if not is_authenticated(required_role='admin'):
        flash('Access denied. Admins only.')
        return redirect(url_for('index'))

    # Get substitute requests and separate them by recent/older
    cutoff_date = datetime.utcnow() - timedelta(days=15)
    recent_requests = SubstituteRequest.query.filter(
        SubstituteRequest.date >= cutoff_date
    ).order_by(SubstituteRequest.date.asc()).all()
    older_requests = SubstituteRequest.query.filter(
        SubstituteRequest.date < cutoff_date
    ).order_by(SubstituteRequest.date.desc()).all()

    # Get all teachers for the create request form
    teachers = User.query.filter_by(role='teacher').order_by(User.name).all()

    return render_template(
        'admin_dashboard.html',
        user=session['user_info'],
        recent_requests=recent_requests,
        older_requests=older_requests,
        teachers=teachers
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
            token=token
        )
        db.session.add(sub_request)
        db.session.commit()

        # Generate dynamic link
        request_link = url_for('view_sub_request', token=token, _external=True)

        # Send notification with link to all substitutes
        substitutes = User.query.filter_by(role='substitute').all()
        subject = "New Substitute Request Available"

        for substitute in substitutes:
            email_body = f"""
            A new substitute request has been posted:

            📅 Date: {date}
            ⏰ Time: {time}
            👨‍🏫 Teacher: {teacher.name}
            📌 Details: {details or 'No additional details provided'}

            👉 Accept the request here: {request_link}
            """
            send_email(subject, substitute.email, email_body)

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

            teacher = get_logged_in_user()

            if teacher:
                token = str(uuid.uuid4())  # Generate unique token

                # Create and save substitute request
                sub_request = SubstituteRequest(
                    teacher_id=teacher.id,
                    date=datetime.strptime(date, '%Y-%m-%d'),
                    time=time,
                    details=details.strip(),
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
                    📌 Details: {details or 'No additional details provided'}

                    👉 Accept the request here: {request_link}
                    """
                    send_email(subject, substitute.email, email_body)

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

        flash("You have successfully accepted the sub request.")
        return redirect(url_for('view_sub_request', token=token))

    return render_template('sub_request.html', sub_request=sub_request, teacher=teacher)


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
