import logging
import secrets
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, render_template, flash, redirect, url_for
from flask_mail import Message
from Package import db_session, bcrypt, app, mail
from Package.models import Users, ResetPassword
from Package.forms import ResetPasswordForm, BeforeResetPassword

bp = Blueprint('password_reset', __name__, url_prefix='/auth')

reset_logger = logging.getLogger('password_reset')
reset_logger.setLevel(logging.DEBUG)

@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    form = BeforeResetPassword()
    is_submitted = request.args.get('submitted',False)
    email = request.args.get('email','')
    if is_submitted :
        return render_template('auth/forgot_password.html', is_submitted=is_submitted, email=email)
    if form.validate_on_submit():
      return redirect(url_for('auth.password_reset.handle_forgot_password',
                              email=form.email.data))
    return render_template('auth/forgot_password.html',
                           form=form)
@bp.route('/handle-forgot-password', methods = ['POST','GET'])
def handle_forgot_password():
    # Add logging to see what's happening
    reset_logger.debug("Handle forgot password route accessed")
    reset_logger.debug(f"Request form data: {request.form}")

    try:
        email = request.args.get('email')
        reset_logger.debug(f"Email extracted: {email}")

        if not email:
            reset_logger.error("No email provided")
            flash("Email is required", "danger")
            return redirect(url_for('auth.password_reset.forgot_password'))

        # Check if the email exists in our database
        reset_logger.debug(f"Looking up user with email: {email}")
        user = db_session.query(Users).filter_by(email=email).first()
        reset_logger.debug(f"User found: {user is not None}")

        if not user:
            reset_logger.warning(f"Password reset requested for non-existent email: {email}")
            # For security reasons, we still show success page
            return redirect(url_for('auth.password_reset.forgot_password', submitted=True, email=email))

        reset_logger.debug(f"User ID: {user.user_id}")

        # Check for existing tokens and remove them
        existing_token = db_session.query(ResetPassword).filter_by(user_id=user.user_id).first()
        if existing_token:
            reset_logger.debug("Removing existing token")
            db_session.delete(existing_token)

        # Generate a secure token
        token = secrets.token_urlsafe(32)
        reset_logger.debug(f"Generated token: {token[:10]}...")

        # FIXED: Store token in database with expiration time
        now = datetime.now(timezone.utc)  # FIXED: Use UTC timezone properly
        expiration = now + timedelta(hours=24)  # FIXED: Use timedelta directly
        reset_logger.debug(f"Token creation time: {now}")
        reset_logger.debug(f"Token expiration time: {expiration}")

        new_token = ResetPassword(
            user_id=user.user_id,
            token=token,
            created_at=now,
            expires_at=expiration
        )

        reset_logger.debug("Adding token to database")
        db_session.add(new_token)
        db_session.commit()
        reset_logger.debug("Token committed to database")

        # Send email with reset link
        reset_logger.debug("Attempting to send email")
        email_sent = send_reset_email(user, token)
        reset_logger.debug(f"Email sent successfully: {email_sent}")

        # Always redirect to success page (for security)
        return redirect(url_for('auth.password_reset.forgot_password', submitted=True, email=email))

    except Exception as e:
        db_session.rollback()
        reset_logger.error(f"Error in handle_forgot_password: {str(e)}", exc_info=True)
        flash("System error occurred. Please try again later.", "danger")
        return redirect(url_for('auth.password_reset.forgot_password'))


@bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    reset_logger.debug("Reset password route accessed")

    form = ResetPasswordForm()
    token = request.args.get('token')
    reset_logger.debug(f"Token from URL: {token[:10] if token else 'None'}...")

    if not token:
        reset_logger.error("No token provided in reset password request")
        flash("Missing or invalid reset link.", "danger")
        return redirect(url_for('auth.login.login'))

    try:
        reset_logger.debug("Looking up token in database")
        token_record = db_session.query(ResetPassword).filter_by(token=token).first()

        if not token_record:
            reset_logger.error(f"Token not found in database: {token[:10]}...")
            flash("Invalid or expired reset link.", "danger")
            return redirect(url_for('auth.login.login'))

        reset_logger.debug(f"Token record found for user_id: {token_record.user_id}")

        # Check if token has expired - FIXED: Use correct field name
        current_time = datetime.now(timezone.utc)
        reset_logger.debug(f"Current time: {current_time}")
        reset_logger.debug(f"Token expires at: {token_record.expires_at}")  # CHANGED: Use Expire_time

        if token_record.expires_at < current_time:  # CHANGED: Use Expire_time
            reset_logger.warning("Token has expired")
            flash("Reset link has expired. Please request a new password reset.", "danger")
            # Clean up expired token
            db_session.delete(token_record)
            db_session.commit()
            return redirect(url_for('auth.password_reset.forgot_password'))

        if request.method == 'POST':
            reset_logger.debug("Processing POST request for password reset")
            reset_logger.debug(f"Form validation result: {form.validate_on_submit()}")
            reset_logger.debug(f"Form errors: {form.errors}")

            if form.validate_on_submit():
                new_password = form.New_Password.data
                confirm_new_password = form.Confirm_New_Password.data

                reset_logger.debug("Form validation passed")
                reset_logger.debug(f"Password length: {len(new_password)}")

                # Additional password match check
                if new_password != confirm_new_password:
                    reset_logger.error("Passwords do not match")
                    flash('Passwords do not match', 'danger')
                    return render_template('auth/reset_password.html', form=form, token=token)

                # Get the actual user
                reset_logger.debug(f"Looking up user with ID: {token_record.user_id}")
                user = db_session.query(Users).filter_by(user_id=token_record.user_id).first()

                if not user:
                    reset_logger.error(f"User not found for user_id: {token_record.user_id}")
                    flash("User account not found.", "danger")
                    return redirect(url_for('auth.login.login'))

                reset_logger.debug("Updating user password")
                # Update user password
                user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')

                # Delete the token record
                db_session.delete(token_record)
                db_session.commit()

                reset_logger.info(f"Password reset successfully for user: {user.email}")
                flash('Your password has been updated successfully!', 'success')
                return redirect(url_for('auth.login.login'))
            else:
                reset_logger.debug("Form validation failed")
                return render_template('auth/reset_password.html', form=form, token=token)

        # GET request - show the form
        return render_template('auth/reset_password.html', form=form, token=token)

    except Exception as e:
        db_session.rollback()
        reset_logger.error(f"Error in reset_password: {str(e)}", exc_info=True)
        flash('Password reset failed. Please try again.', 'danger')
        return redirect(url_for('auth.password_reset.forgot_password'))

def send_reset_email(user, token):

    try:
        # Create password reset link
        reset_link = url_for('auth.password_reset.reset_password', token=token, _external=True)

        # Create and send email
        msg = Message("Password Reset Request", recipients=[user.email]
        )

        msg.body = f"""To reset your password, visit the following link:
{reset_link}

If you did not make this request, please ignore this email and no changes will be made.

This link is valid for 24 hours.
"""

        msg.html = f"""
<p>To reset your password, click on the link below:</p>
<p><a href="{reset_link}">Reset Your Password</a></p>
<p>If you did not make this request, please ignore this email and no changes will be made.</p>
<p>This link is valid for 24 hours.</p>
"""

        mail.send(msg)
        return True
    except Exception as e:
        app.logger.error(f"Failed to send reset email: {str(e)}")
        return False