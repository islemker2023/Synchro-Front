import os
import uuid

from flask import Blueprint, flash, redirect, url_for, request, current_app, render_template, abort, session

from Package import db_session, bcrypt
from Package.condition_login import login_required
from Package.forms import UpdateProfileForm, ChangePasswordForm, ProfilePictureForm
from Package.models import WorkspaceRole, Users
from Package.routes.common.utils import resize_image

bp = Blueprint('profile', __name__)

# Configuration for file uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


@bp.route('/profile')
@bp.route('/profile/<user_id>')
@login_required
def profile(user_id=None):
    """
    Profile route that works for all roles (admin, teacher, delegate, member)
    - If no user_id provided, shows current user's profile
    - If user_id provided, checks permissions before showing that user's profile
    """
    current_user_id = session.get('user_id')
    current_user=db_session.query(Users).filter(Users.user_id==current_user_id).first()
    if user_id:
        # Check if current user can view other user's profile
        if str(current_user.user_id) != user_id:
            # Only allow if current user is an admin in any workspace
            is_admin_anywhere = any(
                membership.role == WorkspaceRole.ADMIN
                for membership in current_user.workspace_memberships
                if membership.is_active
            )
            if not is_admin_anywhere:
                abort(403)  # Forbidden

        # Get the target user
        target_user = db_session.query(Users).filter_by(user_id=user_id).first()
        if not target_user:
            abort(404)  # User not found
    else:
        target_user = current_user

    # Initialize forms
    profile_form = UpdateProfileForm()
    password_form = ChangePasswordForm()
    picture_form = ProfilePictureForm()

    # Only allow editing own profile
    can_edit = (target_user.user_id == current_user.user_id)

    if not can_edit:
        # If viewing someone else's profile, just show read-only view
        return render_template('common/profile_view.html',
                               user=target_user,
                               current_user=current_user)

    # Handle form submissions (only for own profile)
    if request.method == 'POST':
        return handle_profile_forms(profile_form, password_form, picture_form)

    # Pre-populate forms with current user data for GET requests
    if request.method == 'GET':
        profile_form.full_name.data = current_user.full_name
        profile_form.email.data = current_user.email

    return render_template('common/profile.html',
                           user=current_user,
                           profile_form=profile_form,
                           password_form=password_form,
                           picture_form=picture_form,
                           can_edit=can_edit)


@bp.route('/profile/update', methods=['POST'])
@login_required
def handle_profile_forms(profile_form=None, password_form=None, picture_form=None):
    """
    Handle all profile form submissions
    Works for all roles - no role-specific restrictions needed for basic profile operations
    """

    # Initialize forms if not provided
    if not profile_form:
        profile_form = UpdateProfileForm()
    if not password_form:
        password_form = ChangePasswordForm()
    if not picture_form:
        picture_form = ProfilePictureForm()
    current_user_id = session.get('user_id')
    current_user = db_session.query(Users).filter(Users.user_id == current_user_id).first()

    # Handle Profile Update Form
    if profile_form.validate_on_submit() and 'update_profile' in request.form:
        try:
            current_user.full_name = profile_form.full_name.data.strip()
            current_user.email = profile_form.email.data.lower().strip()
            db_session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile.profile'))
        except Exception as e:
            db_session.rollback()
            flash('An error occurred while updating your profile. Please try again.', 'error')
            print(f"Error updating profile: {e}")

    # Handle Password Change Form
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
                return redirect(url_for('common.profile.profile'))
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
                    return redirect(url_for('common.profile.profile'))

            except Exception as e:
                db_session.rollback()
                flash('An error occurred while uploading your profile picture. Please try again.', 'error')
                print(f"Error uploading profile picture: {e}")

    # Handle Remove Picture Request (separate button)
    if request.method == 'POST' and 'remove_picture' in request.form:
        try:
            if current_user.profile_picture:
                # Delete file from filesystem
                file_path = os.path.join(current_app.static_folder, current_user.profile_picture)
                if os.path.exists(file_path):
                    os.remove(file_path)

                # Remove from database
                current_user.profile_picture = None
                db_session.commit()
                flash('Profile picture removed successfully!', 'success')
            else:
                flash('No profile picture to remove.', 'info')
            return redirect(url_for('common.profile.profile'))
        except Exception as e:
            db_session.rollback()
            flash('An error occurred while removing your profile picture. Please try again.', 'error')
            print(f"Error removing profile picture: {e}")

    # If we get here, redirect back to profile
    return redirect(url_for('common.profile.profile'))


@bp.route('/profile/role-info')
@login_required
def role_info():
    """
    Get current user's role information across all workspaces
    Useful for displaying role-specific information in profile
    """
    user_roles = []
    current_user_id = session.get('user_id')
    current_user=db_session.query(Users).filter(Users.user_id==current_user_id).first()
    for membership in current_user.workspace_memberships:
        if membership.is_active:
            user_roles.append({
                'workspace_name': membership.workspace.name,
                'role': membership.role.value,
                'joined_at': membership.joined_at,
                'can_manage': membership.role in [WorkspaceRole.ADMIN, WorkspaceRole.TEACHER]
            })

    return render_template('common/role_info.html', user_roles=user_roles,current_user=current_user_id)


# Helper function to check if user has specific role in any workspace
def user_has_role_anywhere(user, role):
    """Check if user has a specific role in any workspace"""
    return any(
        membership.role == role
        for membership in user.workspace_memberships
        if membership.is_active
    )


# Helper function to get user's primary role (highest permission level)
def get_user_primary_role(user):
    """Get user's highest role across all workspaces"""
    roles = [membership.role for membership in user.workspace_memberships if membership.is_active]

    if WorkspaceRole.ADMIN in roles:
        return WorkspaceRole.ADMIN
    elif WorkspaceRole.TEACHER in roles:
        return WorkspaceRole.TEACHER
    elif WorkspaceRole.DELEGATE in roles:
        return WorkspaceRole.DELEGATE
    else:
        return WorkspaceRole.MEMBER