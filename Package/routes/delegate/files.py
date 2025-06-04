import logging
import traceback

from flask import Blueprint, flash, redirect, url_for, render_template
from sqlalchemy.orm import joinedload

from Package import db_session, Workspace, app
from Package.condition_login import delegate_required, login_required
from Package.models import Folders, Teachers, UploadedFiles
from Package.routes.common.utils import get_workspace_info

bp = Blueprint('files', __name__, url_prefix='/<workspace_id>/delegate')
routes_logger = logging.getLogger('routes/delegate')

@bp.route('/files')
@delegate_required
@login_required
def delegate_files(workspace_id):
    try:
        # Get the current workspace
        workspace = db_session.query(Workspace).filter(
            Workspace.workspace_id == workspace_id,
            Workspace.is_active == True
        ).first()
        if not workspace:
            flash('Workspace not found', 'error')
            return redirect(url_for('delegate_dashboard'))

        # Get all active courses in this workspace with their teachers and files
        folders = db_session.query(Folders).options(
            joinedload(Folders.teacher).joinedload(Teachers.user),
            joinedload(Folders.uploaded_files).joinedload(UploadedFiles.uploader)
        ).filter(
            Folders.workspace_id == workspace_id,
            Folders.is_active == True
        ).order_by(Folders.created_at.desc()).all()

        # Get all uploaded files in this workspace (for the documents table)
        all_files = db_session.query(UploadedFiles).options(
            joinedload(UploadedFiles.folder),
            joinedload(UploadedFiles.uploader)
        ).join(Folders).filter(
            Folders.workspace_id == workspace_id,
            Folders.is_active == True,
            UploadedFiles.is_active == True
        ).order_by(UploadedFiles.uploaded_at.desc()).all()

        workspaces_info = get_workspace_info()
        return render_template('/delegate/files.html',
                               workspaces_info=workspaces_info,
                               workspace=workspace,
                               folders=folders,
                               all_files=all_files)
    except Exception as e:
        flash('Error loading workspaces. Please try again.', 'error')
        app.logger.error(f'Error in files: {str(e)}')
        traceback.print_exc()
        return "Error loading files", 500
