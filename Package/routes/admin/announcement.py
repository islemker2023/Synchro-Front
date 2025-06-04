import logging
import traceback

from flask import render_template, request, flash, redirect, url_for, session, Blueprint
from sqlalchemy import desc
from datetime import datetime

from sqlalchemy.orm import joinedload

from Package import db_session, app
from Package.models import WorkspaceMember, Notices, Workspace
from Package.condition_login import admin_required, login_required
from Package.forms import AnnouncementForm
from Package.routes.common.utils import get_workspace_info

bp = Blueprint('announcement', __name__, url_prefix='/<workspace_id>/admin')
routes_logger = logging.getLogger('routes')

@bp.route('/announcement', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_announcement(workspace_id):
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
        return redirect(url_for('admin.announcement.admin_announcement',workspace_id=workspace_id))

    workspace_id = user_workspace.workspace_id
    form=AnnouncementForm()
    if request.method == 'POST' and form.validate_on_submit():
        title=form.title.data
        description=form.description.data


        try:
            # Create new announcement
            new_notice = Notices(
                workspace_id=workspace_id,
                title=title,
                content=description,
                posted_at=datetime.utcnow(),
                is_active=True,
                user_id=current_user_id
            )

            db_session.add(new_notice)
            db_session.commit()

            flash('Announcement posted successfully!', 'success')
            return redirect(url_for('admin.announcement.admin_announcement',workspace_id=workspace_id))

        except Exception as e:
            db_session.rollback()
            flash(f'Error posting announcement: {str(e)}', 'error')

    # Get all announcements for this workspace
    # Only show announcements from admins, teachers, and delegates
    announcements = db_session.query(Notices).options(
        joinedload(Notices.author)
    ).filter_by(
        workspace_id=workspace_id,
        is_active=True
    ).order_by(desc(Notices.posted_at)).all()
    # Get announcement statistics
    total_announcements = len(announcements)
    recent_announcements = announcements[:5]  # Last 5 announcements

    # Get workspace info
    workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()
    workspaces_info = get_workspace_info()
    try:
        return render_template('admin/announcement.html',
                           workspaces_info=workspaces_info,
                           form=form,
                           total_announcements=total_announcements,
                           recent_announcements=recent_announcements,
                           workspace=workspace)
    except Exception as e:
        flash('Error loading announcement. Please try again.', 'error')
        app.logger.error(f'Error in announcement: {str(e)}')
        traceback.print_exc()
        return "Error loading announcement", 500


@bp.route('/announcement/delete/<notice_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_announcement(notice_id,workspace_id):
    try:
        # Get current user's workspace
        current_user_id = session.get('user_id')

        # Find the announcement
        notice = db_session.query(Notices).filter_by(
            notice_id=notice_id,
            workspace_id=workspace_id,
            is_active=True,
            user_id=current_user_id
        ).first()

        if not notice:
            flash('You do not have permission to delete this announcement', 'error')
        else:
            # Soft delete - set is_active to False
            notice.is_active = False
            db_session.commit()
            flash('Announcement deleted successfully', 'success')

    except Exception as e:
        db_session.rollback()
        flash(f'Error deleting announcement: {str(e)}', 'error')

    return redirect(url_for('admin.admin_announcement'))


@bp.route('/announcement/edit/<notice_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_announcement(notice_id,workspace_id):
    # Get current user's workspace
    current_user_id = session.get('user_id')
    # Find the announcement
    notice = db_session.query(Notices).filter_by(
        notice_id=notice_id,
        workspace_id=workspace_id,
        is_active=True,
        user_id=current_user_id
    ).first()

    if not notice:
        flash('Announcement not found', 'error')
        return redirect(url_for('admin.admin_announcement'))
    form=AnnouncementForm
    if request.method == 'POST' and form.validate_on_submit:
        title = form.title.data
        content =form.description.data

        try:
            notice.title = title
            notice.content = content
            db_session.commit()

            flash('Announcement updated successfully!', 'success')
            return redirect(url_for('admin.admin_announcement'))

        except Exception as e:
            db_session.rollback()
            flash(f'Error updating announcement: {str(e)}', 'error')

    return render_template('admin/announcement.html',form=form, notice=notice)