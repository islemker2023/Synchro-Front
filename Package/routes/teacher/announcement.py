import logging

from flask import render_template, request, flash, redirect, url_for, session, Blueprint
from sqlalchemy import desc
from datetime import datetime

from Package import db_session
from Package.models import WorkspaceMember, Notices, Workspace
from Package.condition_login import admin_required, login_required


bp = Blueprint('announcement', __name__, url_prefix='/routes/announcement')
routes_logger = logging.getLogger('routes')

@bp.route('/<workspace_id>/teacher/announcement', methods=['GET', 'POST'])
@admin_required
@login_required
def admin_announcement():
    # Get current user's workspace
    current_user_id = session.get('user_id')

    # Get user's workspace (assuming admin is part of a workspace)
    user_workspace = db_session.query(WorkspaceMember).filter_by(
        user_id=current_user_id,
        is_active=True
    ).first()

    if not user_workspace:
        flash('No workspace found for user', 'error')
        return redirect(url_for('admin.admin_dashboard'))

    workspace_id = user_workspace.workspace_id

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()

        # Validation
        if not title:
            flash('Title is required', 'error')
        elif not content:
            flash('Content is required', 'error')
        elif len(title) > 255:
            flash('Title must be less than 255 characters', 'error')
        else:
            try:
                # Create new announcement
                new_notice = Notices(
                    workspace_id=workspace_id,
                    title=title,
                    content=content,
                    posted_at=datetime.utcnow(),
                    is_active=True
                )

                db_session.add(new_notice)
                db_session.commit()

                flash('Announcement posted successfully!', 'success')
                return redirect(url_for('admin.admin_announcement'))

            except Exception as e:
                db_session.rollback()
                flash(f'Error posting announcement: {str(e)}', 'error')

    # Get all announcements for this workspace
    # Only show announcements from admins, teachers, and delegates
    announcements = db_session.query(Notices).filter_by(
        workspace_id=workspace_id,
        is_active=True
    ).order_by(desc(Notices.posted_at)).all()

    # Get announcement statistics
    total_announcements = len(announcements)
    recent_announcements = announcements[:5]  # Last 5 announcements

    # Get workspace info
    workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()

    return render_template('admin/announcement.html',
                           announcements=announcements,
                           total_announcements=total_announcements,
                           recent_announcements=recent_announcements,
                           workspace=workspace)


@bp.route('/admin/announcement/delete/<notice_id>', methods=['POST'])
@admin_required
@login_required
def delete_announcement(notice_id):
    try:
        # Get current user's workspace
        current_user_id = session.get('user_id')
        user_workspace = db_session.query(WorkspaceMember).filter_by(
            user_id=current_user_id,
            is_active=True
        ).first()

        if not user_workspace:
            flash('No workspace found', 'error')
            return redirect(url_for('admin.admin_announcement'))

        # Find the announcement
        notice = db_session.query(Notices).filter_by(
            notice_id=notice_id,
            workspace_id=user_workspace.workspace_id
        ).first()

        if not notice:
            flash('Announcement not found', 'error')
        else:
            # Soft delete - set is_active to False
            notice.is_active = False
            db_session.commit()
            flash('Announcement deleted successfully', 'success')

    except Exception as e:
        db_session.rollback()
        flash(f'Error deleting announcement: {str(e)}', 'error')

    return redirect(url_for('admin.admin_announcement'))


@bp.route('/admin/announcement/edit/<notice_id>', methods=['GET', 'POST'])
@admin_required
@login_required
def edit_announcement(notice_id):
    # Get current user's workspace
    current_user_id = session.get('user_id')
    user_workspace = db_session.query(WorkspaceMember).filter_by(
        user_id=current_user_id,
        is_active=True
    ).first()

    if not user_workspace:
        flash('No workspace found', 'error')
        return redirect(url_for('admin.admin_announcement'))

    # Find the announcement
    notice = db_session.query(Notices).filter_by(
        notice_id=notice_id,
        workspace_id=user_workspace.workspace_id,
        is_active=True
    ).first()

    if not notice:
        flash('Announcement not found', 'error')
        return redirect(url_for('admin.admin_announcement'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()

        # Validation
        if not title:
            flash('Title is required', 'error')
        elif not content:
            flash('Content is required', 'error')
        elif len(title) > 255:
            flash('Title must be less than 255 characters', 'error')
        else:
            try:
                notice.title = title
                notice.content = content
                db_session.commit()

                flash('Announcement updated successfully!', 'success')
                return redirect(url_for('admin.admin_announcement'))

            except Exception as e:
                db_session.rollback()
                flash(f'Error updating announcement: {str(e)}', 'error')

    return render_template('admin/edit_announcement.html', notice=notice)