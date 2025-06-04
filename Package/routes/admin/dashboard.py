import traceback
from datetime import datetime

import humanize
from flask import render_template, Blueprint, flash, session
from Package import app, db_session, Workspace
from Package.condition_login import login_required, admin_required
from Package.models import WorkspaceMember, Message, Users
from Package.routes.common.utils import get_workspace_info

bp = Blueprint('admin_dashboard', __name__, url_prefix='/<workspace_id>/admin')
@bp.route('/dashboard')
@login_required
@admin_required
def admin_dashboard(workspace_id):
    try:
        current_user_id = session.get('user_id')
        current_user_email = db_session.query(Users.email).filter_by(
            user_id=current_user_id
        ).scalar()
        recent_messages = db_session.query(Message).filter_by(send_to=current_user_email).order_by(Message.sent_at.desc()).limit(3).all()
        recent_messages_with_time = []
        for msg in recent_messages:
            time_ago = humanize.naturaltime(datetime.utcnow() - msg.sent_at)
            recent_messages_with_time.append({
                'message': msg,
                'time_ago': time_ago
            })
        total_members = db_session.query(WorkspaceMember).filter_by(workspace_id=workspace_id).count()
        workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()
        workspaces_info = get_workspace_info()
        return render_template('admin/dashboard.html',
                               workspace_id=workspace_id,
                               workspaces_info=workspaces_info,
                               workspace=workspace,
                               total_members=total_members,
                               recent_messages_with_time=recent_messages_with_time)
    except Exception as e:
        flash('Error loading workspaces. Please try again.', 'error')
        app.logger.error(f'Error in announcement: {str(e)}')
        traceback.print_exc()
        return "Error loading announcement", 500
