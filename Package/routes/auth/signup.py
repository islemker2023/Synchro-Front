import logging
import uuid
from flask import Blueprint, flash, redirect, url_for, render_template, jsonify, request
from Package import db_session, bcrypt
from Package.models import Users
from Package.forms import SignUpForm
from Package.condition_login import login_not_selected

bp = Blueprint('signup', __name__, url_prefix='/auth')
auth_logger = logging.getLogger('auth')

@bp.route("/signup", methods=['GET', 'POST'])
@login_not_selected
def signup():
    form = SignUpForm()
    print(f"Method: {request.method}")
    print(f"Form validates: {form.validate_on_submit()}")
    if form.errors:
        print(f"Form errors: {form.errors}")
    if form.validate_on_submit():
        try:
            # Check if user already exists
            existing_user = db_session.query(Users).filter_by(email=form.email.data).first()
            if existing_user:
                flash('An account with this email already exists.', 'danger')
                return redirect(url_for('auth.signup.signup'))

            # Create a new user with bcrypt password hashing
            hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')

            # Create new user
            new_user = Users(
                user_id=uuid.uuid4(),
                full_name=form.fullname.data,
                email=form.email.data,
                password_hash=hashed_password
            )

            db_session.add(new_user)
            db_session.commit()

            flash(f'Account created for {form.fullname.data}! You can now log in.', 'success')
            return redirect(url_for('auth.login.login'))
        except Exception as e:
            db_session.rollback()
            auth_logger.error(f"Signup failed for email {form.email.data}: {str(e)}", exc_info=True)
            flash('Registration failed due to system error', 'danger')
            return redirect(url_for('auth.signup.signup'))

    return render_template('auth/signup.html', title='Sign Up', form=form)

@bp.route("/handle-signup", methods=['POST'])
def handle_signup():
    form = SignUpForm()
    try:
        if form.validate_on_submit():
            # Check if user already exists
            existing_user = db_session.query(Users).filter_by(email=form.email.data).first()
            if existing_user:
                return jsonify({"message": "Email already registered", "errors": {"email": ["This email is already registered."]}}), 400

            # Create new user with bcrypt hashing
            hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')

            # Create new user
            new_user = Users(
                user_id=uuid.uuid4(),
                fullname=form.fullname.data,
                email=form.email.data,
                password_hash=hashed_password
            )

            db_session.add(new_user)
            db_session.commit()

            return jsonify({"message": "Account created successfully", "redirect": url_for('auth.login')})
    except Exception as e:
        db_session.rollback()
        auth_logger.error(f"Handle signup failed for email {form.email.data}: {str(e)}", exc_info=True)
        return jsonify({"message": "System error occurred"}), 500
    return jsonify({"message": "Validation failed", "errors": form.errors}), 400