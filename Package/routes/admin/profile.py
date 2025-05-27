import io
import os
import uuid

from PIL.Image import Image
from flask import Blueprint, flash, redirect, url_for, request, current_app, render_template
from flask_login import current_user

from Package import db_session, bcrypt
from Package.condition_login import admin_required, login_required
from Package.forms import UpdateProfileForm, ChangePasswordForm, ProfilePictureForm

bp = Blueprint('admin', __name__)

# Configuration for file uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def resize_image(image_data, max_size=(300, 300)):
    """Resize image to maximum dimensions while maintaining aspect ratio"""
    try:
        image = Image.open(io.BytesIO(image_data))

        # Convert RGBA to RGB if necessary
        if image.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background

        # Resize image
        image.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Save to bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG', quality=85)
        return img_byte_arr.getvalue()
    except Exception as e:
        print(f"Error resizing image: {e}")
        return None


@bp.route('/admin/profile', methods=['GET', 'POST'])
@admin_required
@login_required
def admin_profile():
    # Initialize forms
    profile_form = UpdateProfileForm()
    password_form = ChangePasswordForm()
    picture_form = ProfilePictureForm()

    # Handle Profile Update Form
    if profile_form.validate_on_submit() and 'update_profile' in request.form:
        try:
            current_user.full_name = profile_form.full_name.data.strip()
            current_user.email = profile_form.email.data.lower().strip()
            db_session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('admin.admin_profile'))
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
                return redirect(url_for('admin.admin_profile'))
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
                    return redirect(url_for('admin.admin_profile'))

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
            return redirect(url_for('admin.admin_profile'))
        except Exception as e:
            db_session.rollback()
            flash('An error occurred while removing your profile picture. Please try again.', 'error')
            print(f"Error removing profile picture: {e}")

    # Pre-populate forms with current user data for GET requests
    if request.method == 'GET':
        profile_form.full_name.data = current_user.full_name
        profile_form.email.data = current_user.email

    return render_template('admin/profile.html',
                           user=current_user,
                           profile_form=profile_form,
                           password_form=password_form,
                           picture_form=picture_form)