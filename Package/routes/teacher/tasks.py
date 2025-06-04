import logging
import traceback

from flask import Blueprint, session, flash, redirect, url_for, render_template

from Package import db_session, Workspace, app
from Package.condition_login import delegate_required, login_required
from Package.models import WorkspaceMember, WorkspaceRole, Assignments, Teachers
from Package.routes.common.utils import get_workspace_info

bp = Blueprint('tasks', __name__, url_prefix='/<workspace_id>/teacher')
routes_logger = logging.getLogger('routes/teacher')


@bp.route('/tasks',methods=['GET'])
@delegate_required
@login_required
def teacher_tasks(workspace_id):
    try:
        user_id = session.get('user_id')

        if not user_id:
            return "Unauthorized", 401

        # First check if workspace exists
        workspace = db_session.query(Workspace).filter(
            Workspace.workspace_id == workspace_id,
            Workspace.is_active == True
        ).first()

        if not workspace:
            flash('Workspace not found', 'error')
            return redirect(url_for('teacher.dashboard.teacher_dashboard', workspace_id=workspace_id))

        # Check if user has teacher role in workspace
        membership = db_session.query(WorkspaceMember).filter_by(
            user_id=user_id,
            workspace_id=workspace_id,
            role=WorkspaceRole.TEACHER,
            is_active=True
        ).first()

        if not membership:
            return "You are not a teacher in this workspace", 403

        # Get the teacher record for this user in this workspace
        teacher = db_session.query(Teachers).filter_by(
            user_id=user_id,
            workspace_id=workspace_id
        ).first()

        # Get assignments - either all assignments in workspace or just this teacher's assignments
        if teacher:
            # If teacher record exists, get their specific assignments
            assignments = db_session.query(Assignments).filter_by(
                workspace_id=workspace_id,
                teacher_id=teacher.teacher_id,
                is_active=True
            ).order_by(Assignments.due_date).all()
        else:
            # If no teacher record, get all assignments in workspace
            assignments = db_session.query(Assignments).filter_by(
                workspace_id=workspace_id,
                is_active=True
            ).order_by(Assignments.due_date).all()


        workspaces_info = get_workspace_info()


        return render_template('teacher/tasks.html',
                               assignments=assignments,
                               workspaces_info=workspaces_info,
                               workspace=workspace)
    except Exception as e:
        flash('Error loading workspaces. Please try again.', 'error')
        app.logger.error(f'Error in Objective: {str(e)}')
        traceback.print_exc()
        return "Error loading Objective", 500

