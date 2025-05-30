import traceback

from flask import render_template, Blueprint, flash
from Package import app, db_session, Workspace
from Package.condition_login import login_required, admin_required
from Package.routes.common.utils import get_workspace_info

bp = Blueprint('admin_dashboard', __name__, url_prefix='/<workspace_id>/admin')
@bp.route('/dashboard')
@login_required
@admin_required
def admin_dashboard(workspace_id):
    try:
        workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()
        workspaces_info = get_workspace_info()
        return render_template('admin/dashboard.html',
                               workspaces_info=workspaces_info,
                               workspace=workspace)
    except Exception as e:
        flash('Error loading workspaces. Please try again.', 'error')
        app.logger.error(f'Error in announcement: {str(e)}')
        traceback.print_exc()
        return "Error loading announcement", 500
