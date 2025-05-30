import logging
from flask import render_template, flash, redirect, url_for, session, Blueprint
from sqlalchemy import desc
from Package import db_session
from Package.models import WorkspaceMember, Notices, Workspace
from Package.condition_login import  login_required, delegate_required
from Package.routes.common.utils import get_workspace_info

bp = Blueprint('announcement', __name__, url_prefix='/routes/delegate')
routes_logger = logging.getLogger('routes')

@bp.route('/<workspace_id>/delegate/announcement', methods=['GET', 'POST'])
@login_required
@delegate_required
def delegate_announcement(workspace_id):
    # Get current user's workspace
    current_user_id = session.get('user_id')

    # Get user's workspace (assuming admin is part of a workspace)
    user_workspace = db_session.query(WorkspaceMember).filter_by(
        workspace_id=workspace_id,
        user_id=current_user_id,
        is_active=True
    ).first()

    if not user_workspace:
        flash('No workspace found for user', 'error')
        return redirect(url_for('admin.admin_dashboard'))

    workspace_id = user_workspace.workspace_id

    # Get all announcements for this workspace
    # Only show announcements from admins, teachers, and delegates
    announcements = db_session.query(Notices).filter_by(
        workspace_id=workspace_id,
        is_active=True
    ).order_by(desc(Notices.posted_at)).all()

    # Get announcement statistics
    total_announcements = len(announcements)
    recent_announcements = announcements[:5]  # Last 5 announcements
    workspace_info=get_workspace_info()   # Get workspace info



    return render_template('admin/announcement.html',
                           announcements=announcements,
                           total_announcements=total_announcements,
                           recent_announcements=recent_announcements,
                           workspace_info=workspace_info)


