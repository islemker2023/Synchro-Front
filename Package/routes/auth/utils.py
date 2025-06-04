from flask import session, redirect, url_for, request
import uuid
from Package import db_session
from Package.models import Users


def get_current_user():
    if 'user_id' in session:
        user_id = session['user_id']
        return db_session.query(Users).filter_by(user_id=uuid.UUID(user_id)).first()
    return None

# Helper function to check if user is logged in
def is_logged_in():
    return 'user_id' in session

# Decorator for requiring login
def login_required(f):
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            return redirect(url_for('auth.login.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Decorator for requiring specific role
def role_required(*roles):
    from functools import wraps
    from flask import abort

    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] not in roles:
                abort(403)  # Forbidden
            return f(*args, **kwargs)
        return decorated_function
    return decorator