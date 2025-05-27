
import uuid

from flask import Blueprint, redirect, url_for, session, flash, request

from Package import db_session, bcrypt, app
from Package.models import Users
from authlib.integrations.flask_client import OAuth

bp = Blueprint('oauth', __name__, url_prefix='/auth')


import secrets




oauth = OAuth(app)

# OAuth setup

oauth.register(
    name='google',
    client_id='1086234362936-o5opg7p6lecnftrui84f03tqr11nni92.apps.googleusercontent.com',
    client_secret='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',
    access_token_url='https://oauth2.googleapis.com/token',
server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={
        'scope': 'openid email profile',
    }
)

@bp.route('/google-login')
def google_login():
    try:
        state = secrets.token_urlsafe(16)
        session['google_oauth_state'] = state
        return oauth.google.authorize_redirect(
            url_for('auth.oauth.google_callback', _external=True),
            state=state
        )
    except Exception as e:
        print(f"❌ OAuth error: {e}")  # add this
        flash(f'OAuth initialization failed: {e}', 'danger')  # now it will show the real error
        return redirect(url_for('auth.login.login'))  # adjust this if needed


@bp.route('/google-callback')
def google_callback():
    # CSRF protection with state
    if request.args.get('state') != session.pop('google_oauth_state', None):
        flash('Invalid state parameter. This could be a CSRF attack.', 'danger')
        return redirect(url_for('auth.login.login'))

    try:
        # ✅ Get token from Google
        token = oauth.google.authorize_access_token()

        # ✅ Get stored nonce and parse ID token with it
        nonce = session.pop('google_oauth_nonce', None)  # Retrieve and remove nonce
        user_info = oauth.google.parse_id_token(token, nonce=nonce)  # Pass nonce here

        if not user_info:
            # Fallback to userinfo endpoint if ID token parsing fails
            user_info = oauth.google.get('userinfo').json()

        google_id = user_info.get('sub') or user_info.get('id')
        email = user_info.get('email')
        full_name = user_info.get('name', email.split('@')[0])

    except Exception as e:
        print("❌ Google login failed:", e)
        flash('Google login failed unexpectedly', 'danger')
        return redirect(url_for('auth.login.login'))

    # Store token
    session['google_token'] = token

    # Find or create user
    user = db_session.query(Users).filter_by(email=email).first()
    if not user:
        random_password = secrets.token_hex(16)
        hashed_password = bcrypt.generate_password_hash(random_password).decode('utf-8')

        user = Users(
            user_id=uuid.uuid4(),
            full_name=full_name,
            email=email,
            password_hash=hashed_password
        )
        db_session.add(user)
        db_session.commit()
        flash('Account created with Google successfully!', 'success')

    # Log in user
    session['connected'] = True
    return redirect(url_for('select_workspace'))