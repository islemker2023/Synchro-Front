import logging

from flask import Blueprint, session, flash, redirect, url_for, render_template

from Package import db_session, Workspace
from Package.condition_login import delegate_required, login_required
from Package.models import WorkspaceMember, WorkspaceRole, Assignments
from Package.routes.common.utils import get_workspace_info

bp = Blueprint('tasks', __name__, url_prefix='/<workspace_id>/delegate')
routes_logger = logging.getLogger('routes/delegate')

@bp.route('/tasks')
@delegate_required
@login_required
def delegate_tasks(workspace_id):
        user_id = session.get('user_id')  # This depends on how you're storing the logged-in user
        if not user_id:
            return "Unauthorized", 401
        workspace = db_session.query(Workspace).filter(
            Workspace.workspace_id == workspace_id,
            Workspace.is_active == True
        ).first()
        if not workspace:
            flash('Workspace not found', 'error')
            return redirect(url_for('delegate_dashboard'))

        # Get delegate record
        membership = db_session.query(WorkspaceMember).filter_by(
            user_id=user_id,
            workspace_id=workspace_id,
            role=WorkspaceRole.DELEGATE,
            is_active=True
        ).first()

        if not membership:
            return "You are not a delegate in this workspace", 403

        # Get active assignments in that workspace
        assignments = db_session.query(Assignments).filter_by(
            workspace_id=workspace_id,
            is_active=True
        ).order_by(Assignments.due_date).all()
        workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()
        workspaces_info = get_workspace_info()
        return render_template('delegate/tasks.html', assignments=assignments,
                               workspaces_info=workspaces_info,
                               workspace=workspace)
