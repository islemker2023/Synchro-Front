from .announcement import bp as announcement_bp
from .calendar import bp as calendar_bp
from .files import bp as files_bp
from .manage_members import bp as manage_members_bp
from .objectives import bp as objectives_bp
from .dashboard import bp as dashboard_bp
from .messages import bp as messages_bp

def init_app(admin_bp):
    admin_bp.register_blueprint(announcement_bp)
    admin_bp.register_blueprint(calendar_bp)
    admin_bp.register_blueprint(files_bp)
    admin_bp.register_blueprint(manage_members_bp)
    admin_bp.register_blueprint(objectives_bp)
    admin_bp.register_blueprint(dashboard_bp)
    admin_bp.register_blueprint(messages_bp)