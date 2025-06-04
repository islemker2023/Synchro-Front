import traceback
from datetime import datetime

import humanize
from flask import render_template, Blueprint, flash
from Package import app, db_session, Workspace
from Package.condition_login import login_required,  teacher_required
from Package.models import WorkspaceMember, Message
from Package.routes.common.utils import get_workspace_info

bp = Blueprint('dashboard', __name__, url_prefix='/<workspace_id>/teacher')
@bp.route('/dashboard')
@login_required
@teacher_required
def teacher_dashboard(workspace_id):
    try:
        recent_messages = db_session.query(Message).order_by(Message.sent_at.desc()).limit(3).all()
        recent_messages_with_time = []
        for msg in recent_messages:
            time_ago = humanize.naturaltime(datetime.utcnow() - msg.sent_at)
            recent_messages_with_time = recent_messages_with_time.append({
                'message': msg,
                'time_ago': time_ago
            })
        total_members= db_session.query(WorkspaceMember).filter_by(workspace_id=workspace_id).count()
        workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()
        workspaces_info = get_workspace_info()
        return render_template('teacher/dashboard.html',
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