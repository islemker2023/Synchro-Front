import logging

from flask import Blueprint, render_template, flash
from flask_login import current_user

from Package import db_session, Workspace, app
from Package.models import WorkspaceMember, Courses, Assignments, Notices
from Package.condition_login import login_required

bp = Blueprint('join_workspace', __name__, url_prefix='/routes/common')
common_logger = logging.getLogger('routes/common')

@bp.route('/select_workspace')
@login_required
def select_workspace():
    """Display user's workspaces with database query"""
    try:
        # Query all active workspace memberships for the current user
        user_workspaces = db_session.query(
            Workspace,
            WorkspaceMember.role,
            WorkspaceMember.joined_at
        ).join(
            WorkspaceMember, Workspace.workspace_id == WorkspaceMember.workspace_id
        ).filter(
            WorkspaceMember.user_id == current_user.user_id,
            WorkspaceMember.is_active == True,
            Workspace.is_active == True
        ).order_by(
            WorkspaceMember.joined_at.desc()
        ).all()

        # Format the data for template
        workspaces_data = []
        for workspace, role, joined_at in user_workspaces:
            # Get workspace statistics
            stats = {
                'total_members': db_session.query(WorkspaceMember).filter(
                    WorkspaceMember.workspace_id == workspace.workspace_id,
                    WorkspaceMember.is_active == True
                ).count(),

                'total_courses': db_session.query(Courses).filter(
                    Courses.workspace_id == workspace.workspace_id,
                    Courses.is_active == True
                ).count(),

                'total_assignments': db_session.query(Assignments).filter(
                    Assignments.workspace_id == workspace.workspace_id,
                    Assignments.is_active == True
                ).count(),

                'recent_notices': db_session.query(Notices).filter(
                    Notices.workspace_id == workspace.workspace_id,
                    Notices.is_active == True
                ).count()
            }

            workspaces_data.append({
                'workspace': workspace,
                'role': role,
                'joined_at': joined_at,
                'stats': stats
            })

        return render_template('select_workspace.html', workspaces_data=workspaces_data)

    except Exception as e:
        flash('Error loading workspaces. Please try again.', 'error')
        app.logger.error(f'Error in select_workspace: {str(e)}')
        return render_template('select_workspace.html', workspaces_data=[])



# Helper route to list user's workspaces (useful for navigation)
@bp.route('/my_workspaces')
@login_required
def my_workspaces():
    """Display all workspaces the user is a member of"""
    user_workspaces = current_user.get_workspaces()
    return render_template('my_workspaces.html', workspaces=user_workspaces)