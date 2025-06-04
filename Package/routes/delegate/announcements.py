import logging
import traceback

from flask import Blueprint, flash, render_template
from sqlalchemy import desc

from Package import db_session, app
from Package.condition_login import delegate_required, login_required
from Package.models import  Notices, Workspace
from Package.routes.common.utils import get_workspace_info

bp = Blueprint('announcement', __name__, url_prefix='/<workspace_id>/delegate')
routes_logger = logging.getLogger('routes')

@bp.route('/announcement')
@login_required
@delegate_required
def delegate_announcement(workspace_id):
    try:

        announcements = db_session.query(Notices).filter_by(
            workspace_id=workspace_id,
            is_active=True
        ).order_by(desc(Notices.posted_at)).all()

        # Get announcement statistics
        total_announcements = len(announcements)
        recent_announcements = announcements[:5]  # Last 5 announcements

        # Get workspace info
        workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()
        workspaces_info = get_workspace_info()

        return render_template('delegate/announcement.html',
                                workspaces_info = workspaces_info,
                               announcements=announcements,
                               total_announcements=total_announcements,
                               recent_announcements=recent_announcements,
                               workspace=workspace)
    except Exception as e:
        flash('Error loading workspaces. Please try again.', 'error')
        app.logger.error(f'Error in announcement: {str(e)}')
        traceback.print_exc()
        return "Error loading announcement", 500

