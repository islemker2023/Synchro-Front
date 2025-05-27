import logging

from flask import render_template, request, Blueprint, flash, redirect, url_for
from sqlalchemy.orm import joinedload

from Package import db_session
from Package.models import Workspace, Courses, Teachers, Users, UploadedFiles
from Package.condition_login import admin_required, login_required

bp = Blueprint('files', __name__, url_prefix='/routes/admin')
routes_logger = logging.getLogger('routes/admin')


@bp.route('/<workspace_id>/admin/files')
@admin_required
@login_required
def admin_files(workspace_id):
    # Get the current workspace
    workspace = db_session.query(Workspace).filter(
        Workspace.workspace_id == workspace_id,
        Workspace.is_active == True
    ).first()

    if not workspace:
        flash('Workspace not found', 'error')
        return redirect(url_for('admin_dashboard'))

    # Get all active courses in this workspace with their teachers and files
    courses = db_session.query(Courses).options(
        joinedload(Courses.teacher).joinedload(Teachers.user),
        joinedload(Courses.uploaded_files).joinedload(UploadedFiles.uploader)
    ).filter(
        Courses.workspace_id == workspace_id,
        Courses.is_active == True
    ).order_by(Courses.created_at.desc()).all()

    # Get all uploaded files in this workspace (for the documents table)
    all_files = db_session.query(UploadedFiles).options(
        joinedload(UploadedFiles.course),
        joinedload(UploadedFiles.uploader)
    ).join(Courses).filter(
        Courses.workspace_id == workspace_id,
        Courses.is_active == True,
        UploadedFiles.is_active == True
    ).order_by(UploadedFiles.uploaded_at.desc()).all()

    return render_template('/admin/files.html',
                           workspace=workspace,
                           courses=courses,
                           all_files=all_files)