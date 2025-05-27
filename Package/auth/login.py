import secrets

from flask import render_template, request, jsonify, flash, redirect, url_for, session, Blueprint, current_app

from Package.models import Users
from Package.condition_login import login_required
from Package.forms import LoginForm
from Package import db_session, bcrypt
from datetime import timedelta, datetime
import logging

bp = Blueprint('login', __name__, url_prefix='/auth')
auth_logger = logging.getLogger('auth')

REMEMBER_COOKIE_NAME = 'remember_token'
REMEMBER_DURATION = timedelta(days=30)


def set_remember_cookie(response, user_id):
    """Set secure remember me cookie"""
    token = secrets.token_urlsafe(32)
    expires = datetime.now() + REMEMBER_DURATION

    try:
        # Store token in database (you'll need to add this to your Users model)
        user = db_session.query(Users).get(user_id)
        user.remember_token = token
        user.remember_token_expiry = expires
        db_session.commit()

        response.set_cookie(
            REMEMBER_COOKIE_NAME,
            value=f"{user_id}:{token}",
            expires=expires,
            httponly=True,
            secure=True,  # Only send over HTTPS
            samesite='Lax'
        )
        return response
    except Exception as e:
        db_session.rollback()
        auth_logger.error(f"Failed to set remember cookie: {str(e)}")
        return response


def clear_remember_cookie(response):
    """Clear remember me cookie"""
    response.set_cookie(
        REMEMBER_COOKIE_NAME,
        value='',
        expires=0,
        httponly=True,
        secure=True,
        samesite='Lax'
    )
    return response


# def check_remember_cookie():
#     """Check remember me cookie and log in if valid"""
#     cookie = request.cookies.get(REMEMBER_COOKIE_NAME)
#     if not cookie:
#         return None
#
#     try:
#         user_id, token = cookie.split(':', 1)
#         user = db_session.query(Users).filter_by(
#             user_id=user_id,
#             remember_token=token,
#         ).first()
#
#         if user and user.remember_token_expiry and user.remember_token_expiry > datetime.now():
#             session['user_id'] = str(user.user_id)
#             session.permanent = True
#             return user
#     except Exception as e:
#         auth_logger.warning(f"Invalid remember token: {str(e)}")
#     return None


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Traditional HTML form login - handles both GET (show form) and POST (process form)"""

    # Check if user is already logged in
    if request.method == 'GET' and session.get('connected'):
        flash('You are already logged in!', 'info')
        return redirect(url_for('select_workspace'))

    form = LoginForm()

    # Handle form submission
    if request.method == 'POST' and form.validate_on_submit():
        try:
            # Look up the user by email
            user = db_session.query(Users).filter_by(email=form.email.data).first()

            if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
                # Login successful - set session
                session['connected'] = True

                # Handle "Remember Me" functionality
                if form.remember.data:
                    session.permanent = True
                else:
                    session.permanent = False

                flash('You have been logged in successfully!', 'success')
                return redirect(url_for('select_workspace'))
            else:
                flash('Invalid email or password', 'danger')

        except Exception as e:
            db_session.rollback()
            auth_logger.error(f"Login error: {str(e)}")
            flash('Login failed due to system error', 'danger')

    # Show login form (GET request or failed POST)
    return render_template('auth/login.html', form=form)


# @bp.route("/handle-login", methods=['POST'])
# def handle_login():
#     form = LoginForm()
#     try:
#         if form.validate_on_submit():
#             # Look up the user by email
#             user = db_session.query(Users).filter_by(email=form.email.data).first()
#
#             if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
#                 # Login successful
#                 session['connected'] = True
#                 # Handle "Remember Me" functionality
#                 if form.remember.data:
#                     # Set session to persist for a longer time (30 days)
#                     session.permanent = True
#                     # Get the app's permanent session lifetime setting
#                     current_app.permanent_session_lifetime = timedelta(days=30)
#                 else:
#                     # Default behavior - session expires when browser closes
#                     session.permanent = False
#                 redirect_url = url_for('select_workspace')
#                 return jsonify({"message": "Login successful", "redirect": redirect_url})
#             else:
#                 return jsonify({"message": "Invalid email or password", "errors": {"email": ["Invalid email or password"]}}), 401
#         return jsonify({"message": "Validation failed", "errors": form.errors}), 400
#     except Exception as e:
#         db_session.rollback()
#         auth_logger.error(f"Login error: {str(e)}")
#         return jsonify({"message": "System error occurred"}), 500
#

@bp.route('/logout')
@login_required
def logout():
    try:
        session.pop('connected')
        flash('Logged out successfully', 'success')
        return redirect(url_for('home'))
    except Exception as e:
        db_session.rollback()
        auth_logger.error(f"Logout error: {str(e)}")
        flash('An error occurred during logout', 'danger')
        return redirect(url_for('auth.login'))