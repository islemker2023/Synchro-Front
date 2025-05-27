from .common import bp as common_bp
from .admin import bp as admin_bp
from .delegate import bp as teacher_bp
from .teacher import bp as delegate_bp


def init_app(routes_bp):

    routes_bp.register_blueprint(common_bp)
    routes_bp.register_blueprint(admin_bp)
    routes_bp.register_blueprint(teacher_bp)
    routes_bp.register_blueprint(delegate_bp)