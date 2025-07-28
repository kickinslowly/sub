"""
Helper functions to check if users share schools.
This module contains functions to verify if a level 2 admin shares schools with another user.
"""
from models import User, user_schools
from blueprints.utils.utils import get_logged_in_user
import logging

logger = logging.getLogger(__name__)

def check_shared_schools_access(user_id):
    """
    Check if the current logged-in level 2 admin shares at least one school with the specified user.
    
    Args:
        user_id: The ID of the user to check against
        
    Returns:
        bool: True if the current user is not a level 2 admin or shares at least one school with the specified user,
              False otherwise
    """
    # Get the logged-in user
    logged_in_user = get_logged_in_user()
    
    # If no user is logged in, deny access
    if not logged_in_user:
        logger.warning("No user logged in when checking shared schools access")
        return False
    
    # If the user is not a level 2 admin, allow access (other permission checks should be handled elsewhere)
    if logged_in_user.role != 'admin_l2':
        logger.debug(f"User {logged_in_user.id} is not a level 2 admin, allowing access")
        return True
    
    # If the user is trying to access their own record, allow it
    if str(logged_in_user.id) == str(user_id):
        logger.debug(f"User {logged_in_user.id} is accessing their own record, allowing access")
        return True
    
    # If the level 2 admin has no schools, deny access
    if not logged_in_user.schools:
        logger.warning(f"Level 2 admin {logged_in_user.id} has no schools assigned, denying access")
        return False
    
    # Get the target user
    target_user = User.query.get(user_id)
    if not target_user:
        logger.warning(f"Target user {user_id} not found, denying access")
        return False
    
    # If the target user has no schools, deny access
    if not target_user.schools:
        logger.warning(f"Target user {user_id} has no schools assigned, denying access")
        return False
    
    # Get the admin's school IDs
    admin_school_ids = {school.id for school in logged_in_user.schools}
    
    # Get the target user's school IDs
    user_school_ids = {school.id for school in target_user.schools}
    
    # Check if there's any overlap between the two sets of school IDs
    shared_schools = admin_school_ids.intersection(user_school_ids)
    
    if shared_schools:
        logger.info(f"Level 2 admin {logged_in_user.id} shares schools {shared_schools} with user {user_id}, allowing access")
        return True
    else:
        logger.warning(f"Level 2 admin {logged_in_user.id} does not share any schools with user {user_id}, denying access")
        return False