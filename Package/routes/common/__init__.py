from .common import bp as commonn_bp
from .create_workspace import bp as create_workspace_bp
from .join_workspace import bp as join_workspace_bp
from .profile import bp as profile_bp
from .select_workspace import bp as select_workspace_bp
from .rag import bp as chatbot_bp

def init_app(common_bp):
    common_bp.register_blueprint(commonn_bp)
    common_bp.register_blueprint(create_workspace_bp)
    common_bp.register_blueprint(join_workspace_bp)
    common_bp.register_blueprint(profile_bp)
    common_bp.register_blueprint(select_workspace_bp)
    common_bp.register_blueprint(chatbot_bp)