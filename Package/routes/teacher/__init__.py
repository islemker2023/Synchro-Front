from .announcement import bp as announcement_bp
from .calendar import bp as calendar_bp
from .files import bp as files_bp
from .objectives import bp as objectives_bp

def init_app(teacher_bp):
    teacher_bp.register_blueprint(announcement_bp)
    teacher_bp.register_blueprint(calendar_bp)
    teacher_bp.register_blueprint(files_bp)
    teacher_bp.register_blueprint(objectives_bp)