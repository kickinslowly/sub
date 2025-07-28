"""
Utility functions for the application.
This module contains common functions used across different blueprints.
"""
from flask import session, redirect, url_for
from functools import wraps
from models import User, user_schools
from sqlalchemy.orm import aliased
from sqlalchemy import and_, exists, select
import logging

logger = logging.getLogger(__name__)

def get_logged_in_user():
    """
    Get the currently logged-in user from the database.
    Returns:
        User: The logged-in user object, or None if no user is logged in.
    """
    # First try to get user from user_id in session
    if 'user_id' in session:
        try:
            user = User.query.get(session['user_id'])
            if user:
                return user
        except Exception as e:
            logger.error(f"Error retrieving logged-in user from user_id: {e}")
    
    # If user_id is not available or failed, try user_info
    if 'user_info' in session and 'email' in session['user_info']:
        try:
            user = User.query.filter_by(email=session['user_info']['email']).first()
            if user:
                # Update user_id in session for future use
                session['user_id'] = user.id
                return user
        except Exception as e:
            logger.error(f"Error retrieving logged-in user from user_info: {e}")
    
    return None

def filter_by_organization(query, model=None):
    """
    Filter a query by the organization of the logged-in user.
    Args:
        query: The SQLAlchemy query to filter.
        model: The model class to use for filtering. If None, the model is inferred from the query.
    Returns:
        The filtered query.
    """
    user = get_logged_in_user()
    if user and user.organization_id:
        if model:
            return query.filter(model.organization_id == user.organization_id)
        else:
            # Try to infer the model from the query
            try:
                model = query.column_descriptions[0]['entity']
                return query.filter(model.organization_id == user.organization_id)
            except (IndexError, KeyError, AttributeError) as e:
                logger.error(f"Error filtering by organization: {e}")
                return query
    return query

def filter_by_shared_schools(query, model=None):
    """
    Filter a query to only include users who share at least one school with the logged-in level 2 admin.
    This filter is only applied if the logged-in user is a level 2 admin.
    
    Args:
        query: The SQLAlchemy query to filter.
        model: The model class to use for filtering. If None, the model is inferred from the query.
    
    Returns:
        The filtered query.
    """
    user = get_logged_in_user()
    
    # Log the user information for debugging
    if user:
        logger.info(f"filter_by_shared_schools: User found - ID: {user.id}, Email: {user.email}, Role: {user.role}")
    else:
        logger.warning("filter_by_shared_schools: No user found in session")
        return query
    
    # Only apply the filter for level 2 admins
    if user and user.role == 'admin_l2' and user.schools:
        # Get the IDs of the admin's schools
        admin_school_ids = [school.id for school in user.schools]
        admin_school_names = [school.name for school in user.schools]
        
        # Log the admin's schools for debugging
        logger.info(f"Filtering by shared schools for admin_l2 (ID: {user.id}). Admin schools: {admin_school_names} (IDs: {admin_school_ids})")
        
        if not admin_school_ids:
            logger.warning("Admin has no schools assigned, returning unfiltered query")
            return query
            
        # Determine if we're working with User model or something else
        if model is None:
            try:
                model = query.column_descriptions[0]['entity']
                logger.debug(f"Inferred model for shared schools filter: {model}")
            except (IndexError, KeyError, AttributeError) as e:
                logger.error(f"Error inferring model for shared schools filter: {e}")
                return query
        
        try:
            # Use a join-based approach which is more reliable than exists()
            # This approach works by joining the query with the user_schools table
            # and filtering for rows where the school_id is in the admin's schools
            
            from sqlalchemy import distinct
            
            # Count users before filtering for debugging
            try:
                before_count = query.count()
                logger.debug(f"Before filtering: {before_count} users")
            except Exception as e:
                logger.warning(f"Could not count users before filtering: {e}")
            
            if model == User:
                # For User model queries (most common case)
                logger.debug(f"Using join approach with User model for shared schools filter")
                
                # Create a query that selects distinct user IDs that have schools matching the admin's schools
                filtered_query = query.join(
                    user_schools, 
                    User.id == user_schools.c.user_id
                ).filter(
                    user_schools.c.school_id.in_(admin_school_ids)
                ).distinct()
                
                # Log the SQL query for debugging
                try:
                    sql = str(filtered_query.statement.compile(compile_kwargs={"literal_binds": True}))
                    logger.debug(f"Generated SQL query: {sql}")
                except Exception as e:
                    logger.warning(f"Could not log SQL query: {e}")
                
                # Count users after filtering for debugging
                try:
                    after_count = filtered_query.count()
                    logger.info(f"After filtering: {after_count} users (removed {before_count - after_count})")
                    
                    # Log details of the filtered users for more detailed debugging
                    if after_count <= 20:  # Only log details if there aren't too many users
                        filtered_users = filtered_query.all()
                        for user in filtered_users:
                            user_school_names = [school.name for school in user.schools]
                            logger.info(f"Filtered user: {user.name} (ID: {user.id}, Role: {user.role}) - Schools: {user_school_names}")
                except Exception as e:
                    logger.warning(f"Could not count or log users after filtering: {e}")
                
                logger.info(f"Applied shared schools filter to User query")
                return filtered_query
            else:
                # For other models, try to use the model parameter
                # This assumes the model has an 'id' attribute that corresponds to user_id in user_schools
                logger.debug(f"Using join approach with custom model for shared schools filter: {model}")
                
                # Try to join with user_schools using the model's id
                filtered_query = query.join(
                    user_schools, 
                    model.id == user_schools.c.user_id
                ).filter(
                    user_schools.c.school_id.in_(admin_school_ids)
                ).distinct()
                
                # Log the SQL query for debugging
                try:
                    sql = str(filtered_query.statement.compile(compile_kwargs={"literal_binds": True}))
                    logger.debug(f"Generated SQL query: {sql}")
                except Exception as e:
                    logger.warning(f"Could not log SQL query: {e}")
                
                # Count users after filtering for debugging
                try:
                    after_count = filtered_query.count()
                    logger.info(f"After filtering with custom model: {after_count} users (removed {before_count - after_count})")
                    
                    # Log details of the filtered users for more detailed debugging
                    if after_count <= 20:  # Only log details if there aren't too many users
                        filtered_users = filtered_query.all()
                        for user in filtered_users:
                            try:
                                # Try to get user schools if available
                                if hasattr(user, 'schools'):
                                    user_school_names = [school.name for school in user.schools]
                                    logger.info(f"Filtered user (custom model): {user.name if hasattr(user, 'name') else 'Unknown'} (ID: {user.id}) - Schools: {user_school_names}")
                                else:
                                    logger.info(f"Filtered user (custom model): ID: {user.id} (no schools attribute)")
                            except Exception as e:
                                logger.warning(f"Could not log details for filtered user: {e}")
                except Exception as e:
                    logger.warning(f"Could not count or log users after filtering with custom model: {e}")
                
                logger.info(f"Applied shared schools filter to custom model query")
                return filtered_query
                
        except Exception as e:
            logger.error(f"Error applying shared schools filter: {e}")
            # If there's an error, return the original query
            return query
    
    # For other users or admins without schools, return the original query
    if user:
        if user.role != 'admin_l2':
            logger.info(f"Not applying shared schools filter: User {user.id} is not a level 2 admin (role: {user.role})")
        elif not user.schools:
            logger.info(f"Not applying shared schools filter: Level 2 admin {user.id} has no schools assigned")
        else:
            logger.warning(f"Not applying shared schools filter: Unexpected condition for user {user.id}")
    
    return query


def is_authenticated(required_role=None):
    """
    Check if the current user is authenticated and has the required role.
    Args:
        required_role: The role required to access the resource. If None, any authenticated user can access.
    Returns:
        bool: True if the user is authenticated and has the required role, False otherwise.
    """
    user = get_logged_in_user()
    if not user:
        return False
    
    if required_role is None:
        return True
    
    return user.role == required_role
