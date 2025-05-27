from .login import bp as login_bp
from .signup import bp as signup_bp
from .oauth import bp as oauth_bp
from .password_reset import bp as password_bp

def init_app(auth_bp):
    auth_bp.register_blueprint(login_bp)
    auth_bp.register_blueprint(signup_bp)
    auth_bp.register_blueprint(oauth_bp)
    auth_bp.register_blueprint(password_bp)
