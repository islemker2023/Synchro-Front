import logging
import os
import uuid
from flask import Blueprint, render_template, session, flash, redirect, url_for, request, current_app
from sqlalchemy import desc
from sqlalchemy.orm import joinedload
from flask_login import current_user
from Package import db_session, bcrypt
from Package.condition_login import login_required, delegate_required
from Package.forms import UpdateProfileForm, ProfilePictureForm, ChangePasswordForm
from Package.models import WorkspaceMember, Notices, Workspace, Folders, Teachers, UploadedFiles, Delegates, \
    Assignments, WorkspaceRole
from Package.routes.common.utils import resize_image

bp = Blueprint('delegate', __name__, url_prefix='/routes')
routes_logger = logging.getLogger('routes')


@bp.route('/delegate/announcement')
@delegate_required
@login_required
def delegate_announcement():
    # Get current user's workspace
    current_user_id = session.get('user_id')

    user_workspace = db_session.query(WorkspaceMember).filter_by(
        user_id=current_user_id,
        is_active=True
    ).first()

    if not user_workspace:
        flash('No workspace found for user', 'error')
        return redirect(url_for('delegate.delegate_dashboard'))
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

    # Get workspace info
    workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()

    return render_template('delegate/announcement.html',
                           announcements=announcements,
                           total_announcements=total_announcements,
                           recent_announcements=recent_announcements,
                           workspace=workspace)

@bp.route('/delegate/dashboard')
@delegate_required
@login_required
def delegate_dashboard():
    return render_template('/delegate/dashboard.html')

@bp.route('/delegate/messages')
@delegate_required
@login_required
def delegate_messages():
    return render_template('/delegate/messages.html')

@bp.route('/<workspace_id>/delegate/tasks')
@delegate_required
@login_required
def delegate_tasks(workspace_id):
        user_id = session.get('user_id')  # This depends on how you're storing the logged-in user
        if not user_id:
            return "Unauthorized", 401
        workspace = db_session.query(Workspace).filter(
            Workspace.workspace_id == workspace_id,
            Workspace.is_active == True
        ).first()
        if not workspace:
            flash('Workspace not found', 'error')
            return redirect(url_for('delegate_dashboard'))

        # Get delegate record
        membership = db_session.query(WorkspaceMember).filter_by(
            user_id=user_id,
            workspace_id=workspace_id,
            role=WorkspaceRole.DELEGATE,
            is_active=True
        ).first()

        if not membership:
            return "You are not a delegate in this workspace", 403

        # Get active assignments in that workspace
        assignments = db_session.query(Assignments).filter_by(
            workspace_id=workspace_id,
            is_active=True
        ).order_by(Assignments.due_date).all()

        return render_template('delegate/tasks.html', assignments=assignments)

@bp.route('/<workspace_id>/delegate/files')
@delegate_required
@login_required
def delegate_files(workspace_id):
    # Get the current workspace
    workspace = db_session.query(Workspace).filter(
        Workspace.workspace_id == workspace_id,
        Workspace.is_active == True
    ).first()
    if not workspace:
        flash('Workspace not found', 'error')
        return redirect(url_for('delegate_dashboard'))

    # Get all active courses in this workspace with their teachers and files
    courses = db_session.query(Folders).options(
        joinedload(Folders.teacher).joinedload(Teachers.user),
        joinedload(Folders.uploaded_files).joinedload(UploadedFiles.uploader)
    ).filter(
        Folders.workspace_id == workspace_id,
        Folders.is_active == True
    ).order_by(Folders.created_at.desc()).all()

    # Get all uploaded files in this workspace (for the documents table)
    all_files = db_session.query(UploadedFiles).options(
        joinedload(UploadedFiles.course),
        joinedload(UploadedFiles.uploader)
    ).join(Folders).filter(
        Folders.workspace_id == workspace_id,
        Folders.is_active == True,
        UploadedFiles.is_active == True
    ).order_by(UploadedFiles.uploaded_at.desc()).all()

    return render_template('/delegate/files.html',
                           workspace=workspace,
                           courses=courses,
                           all_files=all_files)

@bp.route('/delegate/calendar')
@delegate_required
@login_required
def delegate_calendar():
    return render_template('/delegate/calendar.html')

@bp.route('/delegate/profile')
@delegate_required
@login_required
def delegate_profile():
    profile_form = UpdateProfileForm()
    password_form = ChangePasswordForm()
    picture_form = ProfilePictureForm()
    if profile_form.validate_on_submit() and 'update_profile' in request.form:
        try:
            current_user.full_name = profile_form.full_name.data.strip()
            current_user.email = profile_form.email.data.lower().strip()
            db_session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('delegate.delegate_profile'))
        except Exception as e:
            db_session.rollback()
            flash('An error occurred while updating your profile. Please try again.', 'error')
            print(f"Error updating profile: {e}")
    if password_form.validate_on_submit() and 'change_password' in request.form:
        # Verify current password
        if not bcrypt.checkpw(password_form.current_password.data.encode('utf-8'),
                              current_user.password_hash.encode('utf-8')):
            flash('Current password is incorrect.', 'error')
        else:
            try:
                # Hash new password with bcrypt
                salt = bcrypt.gensalt()
                hashed_password = bcrypt.hashpw(password_form.new_password.data.encode('utf-8'), salt)
                current_user.password_hash = hashed_password.decode('utf-8')
                db_session.commit()
                flash('Password changed successfully!', 'success')
                return redirect(url_for('delegate.delegate_profile'))
            except Exception as e:
                db_session.rollback()
                flash('An error occurred while changing your password. Please try again.', 'error')
                print(f"Error changing password: {e}")
    # Handle Profile Picture Upload Form
    if picture_form.validate_on_submit() and 'upload_picture' in request.form:
        file = picture_form.profile_picture.data

        if file:
            try:
                # Read file data
                file_data = file.read()

                # Resize image
                resized_image_data = resize_image(file_data)
                if resized_image_data is None:
                    flash('Invalid image file. Please upload a valid image.', 'error')
                else:
                    # Generate unique filename
                    file_extension = 'jpg'  # We convert all to JPEG
                    filename = f"{uuid.uuid4().hex}.{file_extension}"

                    # Ensure upload directory exists
                    upload_dir = os.path.join(current_app.static_folder, 'uploads', 'profiles')
                    os.makedirs(upload_dir, exist_ok=True)

                    # Save file
                    file_path = os.path.join(upload_dir, filename)
                    with open(file_path, 'wb') as f:
                        f.write(resized_image_data)

                    # Delete old profile picture if it exists
                    if current_user.profile_picture:
                        old_file_path = os.path.join(current_app.static_folder, current_user.profile_picture)
                        if os.path.exists(old_file_path):
                            try:
                                os.remove(old_file_path)
                            except:
                                pass  # If we can't delete the old file, it's not critical

                    # Update user's profile picture path
                    current_user.profile_picture = f"uploads/profiles/{filename}"
                    db_session.commit()
                    flash('Profile picture updated successfully!', 'success')
                    return redirect(url_for('delegate.delegate_profile'))

            except Exception as e:
                db_session.rollback()
                flash('An error occurred while uploading your profile picture. Please try again.', 'error')
                print(f"Error uploading profile picture: {e}")
    # Pre-populate forms with current user data for GET requests
    if request.method == 'GET':
        profile_form.full_name.data = current_user.full_name
        profile_form.email.data = current_user.email

    return render_template('delegate/profile.html',
                           user=current_user,
                           profile_form=profile_form,
                           password_form=password_form,
                           picture_form=picture_form)