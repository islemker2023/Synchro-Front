from .announcements import bp as announcements
from .calendar import bp as calendar
from .calendar import api_bp as calendar_api_bp
from .dashboard import bp as dashboard
from .files import bp as files
from .messages import bp as messages
from .tasks import bp as tasks

def init_app(delegate_bp):
    delegate_bp.register_blueprint(announcements)
    delegate_bp.register_blueprint(calendar)
    delegate_bp.register_blueprint(dashboard)
    delegate_bp.register_blueprint(files)
    delegate_bp.register_blueprint(messages)
    delegate_bp.register_blueprint(tasks)
    delegate_bp.register_blueprint(calendar_api_bp)