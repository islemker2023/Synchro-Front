import logging
import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename

from flask import render_template, request, Blueprint, flash, redirect, url_for, jsonify, current_app
from sqlalchemy.orm import joinedload

from Package import db_session, MAX_FILE_SIZE
from Package.models import Workspace, Folders, Teachers, Users, UploadedFiles
from Package.condition_login import admin_required, login_required, teacher_required
from Package.routes.common.utils import ALLOWED_EXTENSIONS, allowed_file, get_file_size, get_file_type

bp = Blueprint('teacher_files', __name__, url_prefix='/routes/teacher')
routes_logger = logging.getLogger('routes/teacher')


@bp.route('/<workspace_id>/teacher/files')
@teacher_required
@login_required
def teacher_files(workspace_id):
    # Get the current workspace
    workspace = db_session.query(Workspace).filter(
        Workspace.workspace_id == workspace_id,
        Workspace.is_active == True
    ).first()

    if not workspace:
        flash('Workspace not found', 'error')
        return redirect(url_for('admin_dashboard'))

    # Get all active folders in this workspace with their teachers and files
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

    return render_template('/admin/files.html',
                           workspace=workspace,
                           folders=folders,
                           all_files=all_files,
                           allowed_extensions=ALLOWED_EXTENSIONS,
                           max_file_size_mb=MAX_FILE_SIZE // (1024 * 1024))


@bp.route('/<workspace_id>/teacher/files/upload', methods=['POST'])
@admin_required
@login_required
def upload_file(workspace_id):
    """Handle file upload to a specific folder"""
    try:
        # Get the current workspace
        workspace = db_session.query(Workspace).filter(
            Workspace.workspace_id == workspace_id,
            Workspace.is_active == True
        ).first()

        if not workspace:
            return jsonify({'success': False, 'message': 'Workspace not found'}), 404

        # Get folder_id from form
        folder_id = request.form.get('folder_id')
        if not folder_id:
            return jsonify({'success': False, 'message': 'Folder ID is required'}), 400

        # Verify folder exists and belongs to workspace
        folder = db_session.query(Folders).filter(
            Folders.folder_id == folder_id,
            Folders.workspace_id == workspace_id,
            Folders.is_active == True
        ).first()

        if not folder:
            return jsonify({'success': False, 'message': 'Folder not found'}), 404

        # Check if files were uploaded
        if 'files' not in request.files:
            return jsonify({'success': False, 'message': 'No files selected'}), 400

        files = request.files.getlist('files')
        if not files or all(file.filename == '' for file in files):
            return jsonify({'success': False, 'message': 'No files selected'}), 400

        uploaded_files = []
        errors = []

        for file in files:
            if file.filename == '':
                continue

            # Validate file
            if not allowed_file(file.filename):
                errors.append(f"File '{file.filename}' has invalid extension")
                continue

            # Check file size
            file_size = get_file_size(file)
            if file_size > MAX_FILE_SIZE:
                size_mb = file_size / (1024 * 1024)
                max_mb = MAX_FILE_SIZE / (1024 * 1024)
                errors.append(f"File '{file.filename}' is too large ({size_mb:.1f}MB > {max_mb}MB)")
                continue

            # Generate secure filename
            original_filename = file.filename
            file_extension = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
            secure_name = secure_filename(original_filename)

            # Generate unique filename to prevent conflicts
            unique_filename = f"{uuid.uuid4().hex}_{secure_name}"

            try:
                # Create upload directory if it doesn't exist
                upload_dir = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'),
                                          'workspace_files', str(workspace_id), str(folder_id))
                os.makedirs(upload_dir, exist_ok=True)

                # Save file
                file_path = os.path.join(upload_dir, unique_filename)
                file.save(file_path)

                # Create file URL (adjust based on your file serving setup)
                file_url = f"/uploads/workspace_files/{workspace_id}/{folder_id}/{unique_filename}"

                # Save file record to database
                uploaded_file = UploadedFiles(
                    folder_id=folder_id,
                    uploaded_by=request.current_user.user_id,  # Assuming you have current_user available
                    file_name=unique_filename,
                    original_filename=original_filename,
                    file_url=file_url,
                    file_size=file_size,
                    file_type=get_file_type(original_filename),
                    uploaded_at=datetime.utcnow()
                )

                db_session.add(uploaded_file)
                uploaded_files.append({
                    'original_filename': original_filename,
                    'file_size': file_size,
                    'file_type': get_file_type(original_filename)
                })

            except Exception as e:
                routes_logger.error(f"Error uploading file {original_filename}: {str(e)}")
                errors.append(f"Error uploading '{original_filename}': {str(e)}")
                continue

        # Commit successful uploads
        if uploaded_files:
            try:
                db_session.commit()
                routes_logger.info(f"Successfully uploaded {len(uploaded_files)} files to folder {folder_id}")
            except Exception as e:
                db_session.rollback()
                routes_logger.error(f"Database error during file upload: {str(e)}")
                return jsonify({'success': False, 'message': 'Database error occurred'}), 500

        # Prepare response
        if uploaded_files and not errors:
            return jsonify({
                'success': True,
                'message': f'Successfully uploaded {len(uploaded_files)} file(s)',
                'uploaded_count': len(uploaded_files)
            })
        elif uploaded_files and errors:
            return jsonify({
                'success': True,
                'message': f'Uploaded {len(uploaded_files)} file(s) with {len(errors)} error(s)',
                'uploaded_count': len(uploaded_files),
                'errors': errors
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No files were uploaded',
                'errors': errors
            }), 400

    except Exception as e:
        db_session.rollback()
        routes_logger.error(f"Unexpected error in file upload: {str(e)}")
        return jsonify({'success': False, 'message': 'An unexpected error occurred'}), 500


@bp.route('/<workspace_id>/teacher/files/delete/<file_id>', methods=['POST'])
@admin_required
@login_required
def delete_file(workspace_id, file_id):
    """Delete a file (soft delete)"""
    try:
        # Get the file
        file = db_session.query(UploadedFiles).join(Folders).filter(
            UploadedFiles.file_id == file_id,
            Folders.workspace_id == workspace_id,
            UploadedFiles.is_active == True
        ).first()

        if not file:
            return jsonify({'success': False, 'message': 'File not found'}), 404

        # Soft delete the file
        file.is_active = False
        db_session.commit()

        # Optionally, delete the physical file
        try:
            if os.path.exists(file.file_url.lstrip('/')):
                os.remove(file.file_url.lstrip('/'))
        except Exception as e:
            routes_logger.warning(f"Could not delete physical file: {str(e)}")

        routes_logger.info(f"File {file_id} deleted by admin")
        return jsonify({'success': True, 'message': 'File deleted successfully'})

    except Exception as e:
        db_session.rollback()
        routes_logger.error(f"Error deleting file: {str(e)}")
        return jsonify({'success': False, 'message': 'Error deleting file'}), 500


@bp.route('/<workspace_id>/teacher/files/folder/<folder_id>')
@admin_required
@login_required
def folder_files(workspace_id, folder_id):
    """Get files for a specific folder (AJAX endpoint)"""
    try:
        # Verify folder exists and belongs to workspace
        folder = db_session.query(Folders).filter(
            Folders.folder_id == folder_id,
            Folders.workspace_id == workspace_id,
            Folders.is_active == True
        ).first()

        if not folder:
            return jsonify({'success': False, 'message': 'Folder not found'}), 404

        # Get files in folder
        files = db_session.query(UploadedFiles).options(
            joinedload(UploadedFiles.uploader)
        ).filter(
            UploadedFiles.folder_id == folder_id,
            UploadedFiles.is_active == True
        ).order_by(UploadedFiles.uploaded_at.desc()).all()

        files_data = []
        for file in files:
            files_data.append({
                'file_id': str(file.file_id),
                'original_filename': file.original_filename,
                'file_size': file.file_size,
                'file_size_mb': round(file.file_size / (1024 * 1024), 2),
                'file_type': file.file_type,
                'uploaded_at': file.uploaded_at.strftime('%Y-%m-%d %H:%M'),
                'uploader_name': file.uploader.full_name if file.uploader else 'Unknown',
                'file_url': file.file_url
            })

        return jsonify({
            'success': True,
            'folder_name': folder.folder_name,
            'files': files_data
        })

    except Exception as e:
        routes_logger.error(f"Error getting folder files: {str(e)}")
        return jsonify({'success': False, 'message': 'Error retrieving files'}), 500


@bp.route('/<workspace_id>/teacher/files/bulk-delete', methods=['POST'])
@admin_required
@login_required
def bulk_delete_files(workspace_id):
    """Delete multiple files at once"""
    try:
        file_ids = request.json.get('file_ids', [])

        if not file_ids:
            return jsonify({'success': False, 'message': 'No files selected'}), 400

        # Get files to delete
        files = db_session.query(UploadedFiles).join(Folders).filter(
            UploadedFiles.file_id.in_(file_ids),
            Folders.workspace_id == workspace_id,
            UploadedFiles.is_active == True
        ).all()

        if not files:
            return jsonify({'success': False, 'message': 'No valid files found'}), 404

        deleted_count = 0
        for file in files:
            file.is_active = False
            deleted_count += 1

            # Optionally delete physical file
            try:
                if os.path.exists(file.file_url.lstrip('/')):
                    os.remove(file.file_url.lstrip('/'))
            except Exception as e:
                routes_logger.warning(f"Could not delete physical file {file.file_id}: {str(e)}")

        db_session.commit()
        routes_logger.info(f"Bulk deleted {deleted_count} files")

        return jsonify({
            'success': True,
            'message': f'Successfully deleted {deleted_count} file(s)',
            'deleted_count': deleted_count
        })

    except Exception as e:
        db_session.rollback()
        routes_logger.error(f"Error in bulk delete: {str(e)}")
        return jsonify({'success': False, 'message': 'Error deleting files'}), 500