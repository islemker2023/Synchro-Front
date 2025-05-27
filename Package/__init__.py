import secrets
from datetime import timedelta
from flask import Flask, Blueprint, session
from flask_mail import Mail
from flask_bcrypt import Bcrypt
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import create_engine, text
import logging
from logging.handlers import RotatingFileHandler
import os
from Package.models import Base, Users, Workspace

# Create Flask app
app = Flask(__name__,static_folder='package/static')
app.config['SECRET_KEY'] = 'TESTTEST'

# Database Configuration
DB_URL = 'postgresql://root:E41G91VV1s0uEHsxBes7YdgnfzJpqogk@dpg-d0n5fpripnbc73dpbkt0-a.oregon-postgres.render.com/jem3iya'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://root:E41G91VV1s0uEHsxBes7YdgnfzJpqogk@dpg-d0n5fpripnbc73dpbkt0-a.oregon-postgres.render.com/jem3iya'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.permanent_session_lifetime = timedelta(minutes=30)
# Create engine and initialize session properly
engine = create_engine(DB_URL)
# Create all tables from models.py


Base.metadata.create_all(engine)


# Create a session factory bound to the engine
db_session_factory = sessionmaker(bind=engine)
# Create a scoped session for thread safety
db_session = scoped_session(db_session_factory)

# Session Cookie Security Configuration
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# Initialize blueprint and bcrypt
auth = Blueprint('auth', __name__)
bcrypt = Bcrypt(app)  # Initialize Bcrypt with the app

# Initialize Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Or your mail server
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'synchro.no.reply1@gmail.com'  # Your email
app.config['MAIL_PASSWORD'] = 'toepioxwzufcbjme'  # Your email password or app password
app.config['MAIL_DEFAULT_SENDER'] =  'synchro.no.reply1@gmail.com'
app.config['MAIL_MAX_EMAILS'] = 5  # Optional: limits the number of emails sent in a single connection
app.config['MAIL_ASCII_ATTACHMENTS'] = False  # Optional: set to True if you need ASCII attachments
# Initialize Mail
mail = Mail(app)



# Load user callback
def load_user(user_id):
   try:
       return db_session.query(Users).filter_by(user_id=user_id).first()
   except ValueError:
       return None


def configure_logging(app):
    if not os.path.exists('logs'):
        os.mkdir('logs')

    # General application log
    file_handler = RotatingFileHandler(
        'logs/flask_app.log',
        maxBytes=10240,
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)

    # Security/Auth specific log
    auth_handler = RotatingFileHandler(
        'logs/auth.log',
        maxBytes=10240,
        backupCount=5
    )
    auth_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    auth_handler.setLevel(logging.WARNING)
    auth_logger = logging.getLogger('auth')
    auth_logger.addHandler(auth_handler)
    auth_logger.setLevel(logging.WARNING)
    auth_logger.propagate = False

    # Routes specific log
    routes_handler = RotatingFileHandler(
        'logs/routes.log',
        maxBytes=10240,
        backupCount=5
    )
    routes_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    routes_handler.setLevel(logging.WARNING)
    routes_logger = logging.getLogger('routes')  # Fixed name
    routes_logger.addHandler(routes_handler)
    routes_logger.setLevel(logging.WARNING)
    routes_logger.propagate = False

    # Set the main app logger level
    app.logger.setLevel(logging.INFO)

    # Log startup message
    app.logger.info('Flask application startup')


# Call this after app creation
configure_logging(app)

# Register teardown context to remove session after each request
@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


@app.context_processor
def inject_csrf_token():
    def generate_csrf_token():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(16)
        return session['csrf_token']
    return dict(csrf_token=generate_csrf_token)


# Import and register auth blueprint
from Package.auth import init_app
from Package import routes
auth_bp = Blueprint('auth', __name__)
routes_bp = Blueprint('routes', __name__)
init_app(auth_bp)
init_app(routes_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(routes_bp)