"""
Super Admin routes for the application.
"""
from flask import render_template, redirect, url_for, flash, request, session, jsonify
from . import super_admin_bp
from models import User, Organization, School, Grade, Subject, SubstituteRequest, user_schools
from extensions import db
from helpers import requires_role
from blueprints.utils.utils import get_logged_in_user
import logging

logger = logging.getLogger(__name__)

# Special route to create the first super admin user
@super_admin_bp.route('/create_first_super_admin', methods=['GET', 'POST'])
@requires_role('admin_l1')  # Only level 1 admins can create the first super admin
def create_first_super_admin():
    """
    Special route to create the first super admin user.
    This can only be accessed by an existing admin_l1 user.
    """
    # Check if a super admin already exists
    existing_super_admin = User.query.filter_by(role='super_admin').first()
    if existing_super_admin:
        flash('A super admin user already exists', 'error')
        return redirect(url_for('admin.dashboard'))
    
    if request.method == 'POST':
        # Get form data
        user_id = request.form.get('user_id')
        
        if not user_id:
            flash('User ID is required', 'error')
            return redirect(url_for('super_admin.create_first_super_admin'))
        
        # Get the user to promote
        user = User.query.get(user_id)
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('super_admin.create_first_super_admin'))
        
        # Promote the user to super admin
        user.role = 'super_admin'
        db.session.commit()
        
        flash(f'User {user.name} has been promoted to Super Admin', 'success')
        
        # If the current user was promoted, redirect to the super admin dashboard
        current_user = get_logged_in_user()
        if current_user and user.id == current_user.id:
            # Update the session role
            session['user_info']['role'] = 'super_admin'
            return redirect(url_for('super_admin.dashboard'))
        else:
            return redirect(url_for('admin.dashboard'))
    
    # For GET requests, render the form
    # Get all admin_l1 users as candidates for promotion
    admin_users = User.query.filter_by(role='admin_l1').all()
    
    return render_template('create_first_super_admin.html', 
                          user=get_logged_in_user(),
                          admin_users=admin_users)

@super_admin_bp.route('/')
@requires_role('super_admin')
def dashboard():
    """
    Super Admin dashboard index route.
    """
    # Get the logged-in user
    user = get_logged_in_user()
    
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('auth.logout'))
    
    # Get all organizations
    organizations = Organization.query.all()
    
    # Get all users
    users = User.query.all()
    
    # Get all schools
    schools = School.query.all()
    
    # Get all substitute requests
    requests = SubstituteRequest.query.all()
    
    return render_template('super_admin_dashboard.html', 
                          user=user,
                          organizations=organizations,
                          users=users,
                          schools=schools,
                          requests=requests)

@super_admin_bp.route('/manage_organizations')
@requires_role('super_admin')
def manage_organizations():
    """
    Route for managing all organizations.
    """
    # Get the logged-in user
    user = get_logged_in_user()
    
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('auth.logout'))
    
    # Get all organizations
    organizations = Organization.query.all()
    
    return render_template('manage_organizations.html', 
                          user=user,
                          organizations=organizations)

@super_admin_bp.route('/manage_all_users')
@requires_role('super_admin')
def manage_all_users():
    """
    Route for managing all users across all organizations.
    """
    # Get the logged-in user
    user = get_logged_in_user()
    
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('auth.logout'))
    
    # Get filter parameters from request
    org_id = request.args.get('org_id')
    role = request.args.get('role')
    search = request.args.get('search')
    
    # Start with a base query
    query = User.query
    
    # Apply filters if provided
    if org_id and org_id.isdigit():
        query = query.filter(User.organization_id == int(org_id))
    
    if role:
        query = query.filter(User.role == role)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter((User.name.ilike(search_term)) | (User.email.ilike(search_term)))
    
    # Get filtered users
    users = query.all()
    
    # Get all organizations for the dropdown
    organizations = Organization.query.all()
    
    # Get all schools for the dropdown
    schools = School.query.all()
    
    # Get all grades and subjects for the dropdowns
    grades = Grade.query.all()
    subjects = Subject.query.all()
    
    return render_template('manage_all_users.html', 
                          user=user,
                          users=users,
                          organizations=organizations,
                          schools=schools,
                          grades=grades,
                          subjects=subjects)

@super_admin_bp.route('/add_organization', methods=['POST'])
@requires_role('super_admin')
def add_organization():
    """
    Route for adding a new organization.
    """
    if request.method == 'POST':
        name = request.form.get('name')
        
        # Validate required fields
        if not name:
            flash('Organization name is required', 'error')
            return redirect(url_for('super_admin.manage_organizations'))
        
        # Check if organization already exists
        existing_org = Organization.query.filter_by(name=name).first()
        if existing_org:
            flash('An organization with this name already exists', 'error')
            return redirect(url_for('super_admin.manage_organizations'))
        
        # Create new organization
        new_org = Organization(name=name)
        
        db.session.add(new_org)
        db.session.commit()
        
        flash('Organization created successfully', 'success')
        return redirect(url_for('super_admin.manage_organizations'))
    
    # If not POST, redirect to manage_organizations
    return redirect(url_for('super_admin.manage_organizations'))

@super_admin_bp.route('/add_user', methods=['POST'])
@requires_role('super_admin')
def add_user():
    """
    Route for adding a new user from the manage_all_users page.
    """
    # Get form data
    name = request.form.get('name')
    email = request.form.get('email')
    role = request.form.get('role')
    phone = request.form.get('phone')
    organization_id = request.form.get('organization_id')

    # Validate required inputs
    if not name or not email or not role:
        flash('All fields (name, email, role) are required!', 'error')
        return redirect(url_for('super_admin.manage_all_users'))

    # Check for duplicate email
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        flash('A user with this email already exists!', 'error')
        return redirect(url_for('super_admin.manage_all_users'))

    # Create the new user
    new_user = User(
        name=name,
        email=email,
        role=role,
        phone=phone,
        organization_id=organization_id if organization_id else None
    )

    # Add and commit changes to the database
    db.session.add(new_user)
    db.session.commit()

    # Flash a success message
    flash(f'User {name} ({email}) added successfully!', 'success')

    return redirect(url_for('super_admin.manage_all_users'))

@super_admin_bp.route('/get_schools_by_organization/<int:org_id>', methods=['GET'])
@requires_role('super_admin')
def get_schools_by_organization(org_id):
    """
    API endpoint to get schools for a specific organization.
    Returns a JSON list of schools with their IDs and names.
    """
    # Query schools for the given organization
    schools = School.query.filter_by(organization_id=org_id).all()
    
    # Format schools as a list of dictionaries
    schools_list = [{'id': school.id, 'name': school.name} for school in schools]
    
    return jsonify(schools_list)


@super_admin_bp.route('/edit_user/<int:user_id>', methods=['POST'])
@requires_role('super_admin')
def edit_user(user_id):
    """
    Route for editing a user from the manage_all_users page.
    """
    # Fetch the user from the database
    user = User.query.get_or_404(user_id)

    # Update basic user details
    user.name = request.form['name']
    user.email = request.form['email']
    user.role = request.form['role']
    user.phone = request.form.get('phone', None)
    
    # Update organization
    organization_id = request.form.get('organization_id')
    if organization_id:
        user.organization_id = organization_id
    else:
        user.organization_id = None
    
    # Get multiple schools
    school_ids = request.form.getlist('schools')  # List of selected school IDs
    school_objs = School.query.filter(School.id.in_(school_ids)).all() if school_ids else []

    # Update schools relationship
    user.schools = school_objs

    # Save changes to the database
    db.session.commit()

    flash(f"User '{user.name}' updated successfully!", 'success')
    return redirect(url_for('super_admin.manage_all_users'))


@super_admin_bp.route('/get_user_schools/<int:user_id>', methods=['GET'])
@requires_role('super_admin')
def get_user_schools(user_id):
    """
    API endpoint to get the schools associated with a specific user.
    Returns a JSON list of school IDs.
    """
    # Query the user_schools association table to get school IDs for the user
    user_school_records = db.session.query(user_schools).filter(user_schools.c.user_id == user_id).all()
    
    # Extract school IDs from the records
    school_ids = [record.school_id for record in user_school_records]
    
    return jsonify(school_ids)


@super_admin_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@requires_role('super_admin')
def delete_user(user_id):
    """
    Route for deleting a user from the manage_all_users page.
    """
    # Find the user to delete
    user = User.query.get_or_404(user_id)

    # Handle all substitute requests related to this user
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

    # Store the user's name before deletion
    user_name = user.name
    
    # Delete the user
    db.session.delete(user)
    db.session.commit()

    flash(f"User '{user_name}' has been removed successfully.", 'success')
    return redirect(url_for('super_admin.manage_all_users'))


@super_admin_bp.route('/create_super_admin', methods=['GET', 'POST'])
@requires_role('super_admin')
def create_super_admin():
    """
    Route for creating a new super admin user.
    """
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        
        # Validate required fields
        if not name or not email:
            flash('Name and email are required', 'error')
            return redirect(url_for('super_admin.create_super_admin'))
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('A user with this email already exists', 'error')
            return redirect(url_for('super_admin.create_super_admin'))
        
        # Get the current user
        current_user = get_logged_in_user()
        
        # Create new super admin user
        new_user = User(
            name=name,
            email=email,
            role='super_admin',
            phone=phone,
            created_by=current_user.id if current_user else None
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Super admin user created successfully', 'success')
        return redirect(url_for('super_admin.dashboard'))
    
    # For GET requests, render the form
    return render_template('create_super_admin.html', user=get_logged_in_user())


@super_admin_bp.route('/edit_organization/<int:org_id>', methods=['POST'])
@requires_role('super_admin')
def edit_organization(org_id):
    """
    Route for editing an organization.
    """
    # Find the organization to edit
    organization = Organization.query.get_or_404(org_id)
    
    if request.method == 'POST':
        # Get the new name from the form
        name = request.form.get('name')
        
        # Validate required fields
        if not name:
            flash('Organization name is required', 'error')
            return redirect(url_for('super_admin.manage_organizations'))
        
        # Check if another organization with this name already exists
        existing_org = Organization.query.filter(Organization.name == name, Organization.id != org_id).first()
        if existing_org:
            flash('An organization with this name already exists', 'error')
            return redirect(url_for('super_admin.manage_organizations'))
        
        # Update the organization name
        organization.name = name
        
        # Handle adding a new school
        add_school_name = request.form.get('add_school_name')
        add_school_code = request.form.get('add_school_code')
        
        if add_school_name and add_school_code:
            # Check if a school with this name or code already exists
            existing_school = School.query.filter(
                (School.name == add_school_name) | (School.code == add_school_code)
            ).first()
            
            if existing_school:
                if existing_school.name == add_school_name:
                    flash(f'A school with the name "{add_school_name}" already exists.', 'error')
                else:
                    flash(f'A school with the code "{add_school_code}" already exists.', 'error')
            else:
                # Create new school and add it to the organization
                new_school = School(
                    name=add_school_name,
                    code=add_school_code,
                    organization_id=organization.id
                )
                db.session.add(new_school)
                flash(f'School "{add_school_name}" added successfully.', 'success')
        
        # Handle removing schools
        schools_to_remove = request.form.getlist('remove_school')
        for school_id in schools_to_remove:
            try:
                school_id = int(school_id)
                school = School.query.get(school_id)
                
                if school and school.organization_id == organization.id:
                    # Check if there are users associated with this school
                    users_count = len(school.associated_users)
                    if users_count > 0:
                        flash(f'Cannot remove school "{school.name}" because it has {users_count} users associated with it. Reassign these users to another school first.', 'error')
                        continue
                    
                    # Check if there are substitute requests associated with this school
                    requests_count = SubstituteRequest.query.filter_by(school_id=school_id).count()
                    if requests_count > 0:
                        flash(f'Cannot remove school "{school.name}" because it has {requests_count} substitute requests associated with it.', 'error')
                        continue
                    
                    # Remove the school from the organization
                    db.session.delete(school)
                    flash(f'School "{school.name}" removed successfully.', 'success')
            except Exception as e:
                logger.error(f"Error removing school {school_id}: {str(e)}")
                flash(f'An error occurred while removing a school: {str(e)}', 'error')
        
        db.session.commit()
        flash('Organization updated successfully', 'success')
    
    return redirect(url_for('super_admin.manage_organizations'))


@super_admin_bp.route('/get_organization_schools/<int:org_id>', methods=['GET'])
@requires_role('super_admin')
def get_organization_schools(org_id):
    """
    API route to get schools for a specific organization.
    Returns JSON data of schools.
    """
    # Find the organization
    organization = Organization.query.get_or_404(org_id)
    
    # Get all schools for this organization
    schools = organization.schools
    
    # Convert to JSON-serializable format
    schools_data = [
        {
            'id': school.id,
            'name': school.name,
            'code': school.code
        }
        for school in schools
    ]
    
    return jsonify({'schools': schools_data})


@super_admin_bp.route('/delete_organization/<int:org_id>', methods=['POST'])
@requires_role('super_admin')
def delete_organization(org_id):
    """
    Route for deleting an organization.
    """
    # Find the organization to delete
    organization = Organization.query.get_or_404(org_id)
    
    # Store the organization name for the flash message
    org_name = organization.name
    
    try:
        # Handle associated data
        # 1. Handle users - either delete them or set organization_id to None
        for user in organization.users:
            # Option 1: Delete users
            # db.session.delete(user)
            
            # Option 2: Set organization_id to None (keep users but unlink them)
            user.organization_id = None
        
        # 2. Handle schools - delete them
        for school in organization.schools:
            db.session.delete(school)
        
        # 3. Handle substitute requests - delete them
        for request in organization.substitute_requests:
            db.session.delete(request)
        
        # Finally, delete the organization
        db.session.delete(organization)
        db.session.commit()
        
        flash(f'Organization "{org_name}" and all associated data have been deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting organization {org_id}: {str(e)}")
        flash(f'An error occurred while deleting the organization: {str(e)}', 'error')
    
    return redirect(url_for('super_admin.manage_organizations'))