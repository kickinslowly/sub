"""
User routes for the application.
"""
from flask import render_template, redirect, url_for, session, flash, request, jsonify
from sqlalchemy.exc import SQLAlchemyError
from models import User, SubstituteRequest, Grade, Subject, School
from extensions import db
from . import users_bp
from blueprints.utils.utils import get_logged_in_user, filter_by_organization
from helpers import calculate_total_hours_out, convert_utc_to_local, format_datetime, requires_role
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

@users_bp.route('/dashboard')
def dashboard():
    """Dashboard for teachers."""
    logged_in_user = get_logged_in_user()
    if not logged_in_user:  # Redirect if user is not logged in
        return redirect(url_for('auth.index'))
    past_bookings = (
        filter_by_organization(SubstituteRequest.query, SubstituteRequest)
        .filter_by(teacher_id=logged_in_user.id)
        .order_by(SubstituteRequest.date.desc())
        .all()
    )
    
    # Calculate total hours out
    total_hours_out = calculate_total_hours_out(past_bookings)
    
    return render_template('dashboard.html', user=logged_in_user, past_bookings=past_bookings, total_hours_out=total_hours_out)

@users_bp.route('/profile/<int:user_id>')
def user_profile(user_id):
    # Get the current logged-in user
    current_user = get_logged_in_user()
    if not current_user:
        flash('Please log in to continue.')
        return redirect(url_for('auth.index'))
        
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

@users_bp.route('/edit_profile/<int:user_id>', methods=['GET', 'POST'])
def edit_profile(user_id):
    # Ensure user is authenticated
    logged_in_user = get_logged_in_user()
    if not logged_in_user:
        flash('Please log in to continue.')
        return redirect(url_for('auth.index'))

    # Get the user to edit
    user_to_edit = User.query.get_or_404(user_id)
    
    # Check permissions: user can edit their own profile or admin_l2 can edit any profile
    if logged_in_user.id != user_to_edit.id and logged_in_user.role != 'admin_l2':
        flash('You do not have permission to edit this profile.')
        return redirect(url_for('users.user_profile', user_id=user_id))

    # Ensure user is a teacher, substitute, or admin_l2
    if logged_in_user.role not in ['teacher', 'substitute', 'admin_l2']:
        flash('This feature is only available for teachers, substitutes, and level 2 admins.')
        return redirect(url_for('users.dashboard'))

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
            return redirect(url_for('users.user_profile', user_id=user_id))
        elif user_to_edit.role == 'substitute':
            return redirect(url_for('substitutes.dashboard'))
        else:
            return redirect(url_for('users.dashboard'))

    return render_template('edit_profile.html', user=user_to_edit, grades=grades, subjects=subjects, schools=schools)

@users_bp.route('/api/teacher_bookings')
def api_teacher_bookings():
    """API endpoint to get teacher bookings for reactive dashboard."""
    logged_in_user = get_logged_in_user()
    if not logged_in_user:
        return jsonify({"error": "Not authenticated"}), 401

    # Get all bookings for the teacher
    bookings = SubstituteRequest.query.filter_by(teacher_id=logged_in_user.id).order_by(SubstituteRequest.date.desc()).all()

    # Calculate total hours out
    total_hours_out = calculate_total_hours_out(bookings)

    # Convert bookings to JSON-serializable format
    bookings_data = []
    for booking in bookings:
        # Get user's timezone or default to UTC
        user_timezone = logged_in_user.timezone or 'UTC'
        
        # Convert created_at to user's timezone
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