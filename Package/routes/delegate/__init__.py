from .announcements import bp as announcements
from .calendar import bp as calendar

def init_app(delegate_bp):
    delegate_bp.register_blueprint(announcements)
    delegate_bp.register_blueprint(calendar)