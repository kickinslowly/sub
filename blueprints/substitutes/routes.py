"""
Substitute routes for the application.
"""
from flask import render_template, redirect, url_for, session, flash, request, jsonify
from sqlalchemy.exc import SQLAlchemyError
from models import User, SubstituteRequest, SubstituteUnavailability
from extensions import db
from . import substitutes_bp
from blueprints.utils.utils import get_logged_in_user, filter_by_organization
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

@substitutes_bp.route('/dashboard')
def dashboard():
    """Dashboard for substitute teachers."""
    if 'user_info' not in session or session['user_info']['role'] != 'substitute':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('auth.login'))

    logged_in_user = get_logged_in_user()

    # Check if logged_in_user is None
    if logged_in_user is None:
        flash("User not found. Please log in again.", "danger")
        return redirect(url_for('auth.login'))

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

@substitutes_bp.route('/api/unavailability', methods=['GET', 'POST'])
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

@substitutes_bp.route('/api/unavailability/<int:unavailability_id>', methods=['DELETE'])
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