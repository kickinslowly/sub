"""
Authentication routes for the application.
"""
from flask import render_template, redirect, url_for, session, flash, current_app, request
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from models import User, Organization
from extensions import db, google
from . import auth_bp
from blueprints.utils.utils import get_logged_in_user
import logging

# Try to import Stripe, but don't fail if it's not installed
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    logging.warning("Stripe module not available. Payment processing will be disabled.")

logger = logging.getLogger(__name__)

@auth_bp.route('/')
def index():
    return render_template('login.html')

@auth_bp.route('/create_account', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')
            email = request.form.get('email')
            organization_name = request.form.get('organization')
            phone = request.form.get('phone')
            
            # Validate required fields
            if not all([name, email, organization_name, phone]):
                flash('Name, email, organization, and phone are required', 'error')
                return render_template('create_account.html', 
                                      stripe_publishable_key=current_app.config.get('STRIPE_PUBLISHABLE_KEY'))
            
            # Check if Stripe is available for payment processing
            if STRIPE_AVAILABLE:
                stripe_token = request.form.get('stripeToken')
                
                if not stripe_token:
                    flash('Payment information is required', 'error')
                    return render_template('create_account.html', 
                                          stripe_publishable_key=current_app.config.get('STRIPE_PUBLISHABLE_KEY'))
                
                try:
                    # Initialize Stripe with the secret key
                    stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
                    
                    # Create a customer in Stripe
                    customer = stripe.Customer.create(
                        email=email,
                        name=name,
                        phone=phone,
                        source=stripe_token
                    )
                    
                    # Create a subscription for the customer
                    subscription = stripe.Subscription.create(
                        customer=customer.id,
                        items=[
                            {
                                'price': current_app.config.get('STRIPE_PRICE_ID'),  # Monthly subscription price ID
                            },
                        ],
                    )
                    
                    # If payment is not successful, return with error
                    if subscription.status not in ['active', 'trialing']:
                        flash('Payment processing failed. Please try again.', 'error')
                        return render_template('create_account.html', 
                                              stripe_publishable_key=current_app.config.get('STRIPE_PUBLISHABLE_KEY'))
                        
                except stripe.error.CardError as e:
                    # Since it's a decline, stripe.error.CardError will be caught
                    flash(f'Card error: {e.error.message}', 'error')
                    return render_template('create_account.html', 
                                          stripe_publishable_key=current_app.config.get('STRIPE_PUBLISHABLE_KEY'))
                except stripe.error.RateLimitError as e:
                    # Too many requests made to the API too quickly
                    flash('Rate limit error. Please try again later.', 'error')
                    return render_template('create_account.html', 
                                          stripe_publishable_key=current_app.config.get('STRIPE_PUBLISHABLE_KEY'))
                except stripe.error.InvalidRequestError as e:
                    # Invalid parameters were supplied to Stripe's API
                    flash('Invalid request. Please try again.', 'error')
                    return render_template('create_account.html', 
                                          stripe_publishable_key=current_app.config.get('STRIPE_PUBLISHABLE_KEY'))
                except stripe.error.AuthenticationError as e:
                    # Authentication with Stripe's API failed
                    logger.error(f"Stripe authentication error: {e}")
                    flash('Payment processing failed. Please contact support.', 'error')
                    return render_template('create_account.html', 
                                          stripe_publishable_key=current_app.config.get('STRIPE_PUBLISHABLE_KEY'))
                except stripe.error.APIConnectionError as e:
                    # Network communication with Stripe failed
                    flash('Network error. Please try again.', 'error')
                    return render_template('create_account.html', 
                                          stripe_publishable_key=current_app.config.get('STRIPE_PUBLISHABLE_KEY'))
                except stripe.error.StripeError as e:
                    # Display a very generic error to the user
                    logger.error(f"Stripe error: {e}")
                    flash('Payment processing failed. Please try again later.', 'error')
                    return render_template('create_account.html', 
                                          stripe_publishable_key=current_app.config.get('STRIPE_PUBLISHABLE_KEY'))
                except Exception as e:
                    # Something else happened, completely unrelated to Stripe
                    logger.error(f"Unexpected error during payment processing: {e}")
                    flash('An unexpected error occurred. Please try again later.', 'error')
                    return render_template('create_account.html', 
                                          stripe_publishable_key=current_app.config.get('STRIPE_PUBLISHABLE_KEY'))
            else:
                # If Stripe is not available, log a warning
                logger.warning("Stripe is not available. Creating account without payment processing.")
            
            # Create organization
            organization = Organization(name=organization_name)
            db.session.add(organization)
            db.session.flush()  # Flush to get the organization ID
            
            # Create user as level 1 admin
            user = User(
                name=name,
                email=email,
                role='admin_l1',
                phone=phone,
                organization_id=organization.id
            )
            db.session.add(user)
            db.session.commit()
            
            # Store user information in the session
            session['user_info'] = {'email': user.email, 'role': user.role}
            session['user_id'] = user.id
            
            flash('Your account has been created successfully!', 'success')
            return redirect(url_for('admin.dashboard'))
                
        except Exception as e:
            logger.error(f"Error during account creation: {e}")
            flash('An error occurred during account creation. Please try again.', 'error')
            return render_template('create_account.html', 
                                  stripe_publishable_key=current_app.config.get('STRIPE_PUBLISHABLE_KEY'))
    
    # For GET requests, render the form with Stripe publishable key
    return render_template('create_account.html', 
                          stripe_publishable_key=current_app.config.get('STRIPE_PUBLISHABLE_KEY'))

@auth_bp.route('/login')
def login():
    redirect_uri = url_for('auth.authorized', _external=True)
    return google.authorize_redirect(redirect_uri)

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have successfully logged out.')
    return redirect(url_for('auth.index'))

@auth_bp.route('/authorized')
def authorized():
    try:
        token = google.authorize_access_token()
        user_info = google.get('userinfo').json()

        try:
            # Look for existing user in the database
            user = User.query.filter_by(email=user_info['email']).first()

            # Determine user role
            # Check if the email is in TECH_COORDINATOR_EMAILS (highest level admin)
            if user_info['email'] in current_app.config.get('TECH_COORDINATOR_EMAILS', []):
                role = 'admin_l1'  # Level 1 admin (tech coordinator)
            # Check if the email is in ADMIN_EMAILS (level 2 admins)
            elif user_info['email'] in current_app.config.get('ADMIN_EMAILS', []):
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
                return redirect(url_for('auth.index', login_error=1))
                
            # Ensure existing user has an organization
            if user.organization_id is None and default_org:
                user.organization_id = default_org.id
            
            # Update role if it's missing or if it's the old 'admin' role that needs to be migrated
            if not user.role or (user.role == 'admin' and role in ['admin_l1', 'admin_l2']):
                user.role = role
                logger.debug(f"Updated user role from 'admin' to '{role}'")

            db.session.commit()
        except OperationalError as e:
            # Handle database operational errors (like missing columns)
            logger.error(f"Database operational error during user creation/update: {e}")
            flash("A database error occurred during login. Please contact the administrator.")
            db.session.rollback()
            return redirect(url_for('auth.index'))
        except SQLAlchemyError as e:
            # Handle other SQLAlchemy errors
            logger.error(f"Database error during user creation/update: {e}")
            flash("A database error occurred during login. Please contact the administrator.")
            db.session.rollback()
            return redirect(url_for('auth.index'))

        # Store user information in the session
        session['user_info'] = {'email': user.email, 'role': user.role}
        session['user_id'] = user.id

        logger.debug(f"Role Assigned: {user.role}, Email: {user.email}")

        # Redirect to the correct dashboard based on role
        if user.role == 'super_admin':
            return redirect(url_for('super_admin.dashboard'))
        elif user.role in ['admin_l1', 'admin_l2']:
            return redirect(url_for('admin.dashboard'))
        elif user.role == 'substitute':
            return redirect(url_for('substitutes.dashboard'))
        else:
            return redirect(url_for('users.dashboard'))

    except ValueError as e:
        flash('Invalid response from authentication server')
        logger.error(f"OAuth value error: {e}")
        return redirect(url_for('auth.index'))
    except KeyError as e:
        flash('Missing information in authentication response')
        logger.error(f"Missing key in OAuth response: {e}")
        return redirect(url_for('auth.index'))
    except SQLAlchemyError as e:
        flash('Database error during login')
        logger.error(f"Database error: {e}")
        return redirect(url_for('auth.index'))
    except Exception as e:
        flash('Error during login')
        logger.error(f"Login failed: {e}, User Info: {session.get('user_info', {})}")
        return redirect(url_for('auth.index'))