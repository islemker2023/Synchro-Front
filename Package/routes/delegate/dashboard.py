import logging

from flask import Blueprint, render_template

from Package import db_session
from Package.condition_login import delegate_required, login_required
from Package.models import  Workspace
from Package.routes.common.utils import get_workspace_info

bp = Blueprint('dashboard', __name__, url_prefix='/<workspace_id>/delegate')
routes_logger = logging.getLogger('routes/delegate')

@bp.route('/dashboard')
@login_required
@delegate_required
def delegate_dashboard(workspace_id):

    workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()
    workspaces_info = get_workspace_info()
    return render_template('delegate/dashboard.html',
                           workspaces=workspace,
                           workspaces_info=workspaces_info)