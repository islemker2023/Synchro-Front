import io
import os

from PIL import Image
from flask import session

from Package import ALLOWED_EXTENSIONS, db_session, Workspace
from Package.models import WorkspaceMember


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




def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_size(file):
    """Get file size in bytes"""
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    return size


def get_file_type(filename):
    """Get file MIME type based on extension"""
    extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

    mime_types = {
        'pdf': 'application/pdf',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'ppt': 'application/vnd.ms-powerpoint',
        'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'txt': 'text/plain',
        'csv': 'text/csv',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'mp4': 'video/mp4',
        'mp3': 'audio/mpeg',
        'wav': 'audio/wav',
        'avi': 'video/x-msvideo',
        'mov': 'video/quicktime',
        'zip': 'application/zip',
        'rar': 'application/x-rar-compressed',
        '7z': 'application/x-7z-compressed'
    }

    return mime_types.get(extension, 'application/octet-stream')

def get_workspace_info():
    current_user = session.get('user_id')
    user_workspaces = db_session.query(
            Workspace.name,
            Workspace.description,
            Workspace.workspace_id,
            WorkspaceMember.role,
            WorkspaceMember.joined_at,
        ).join(
            WorkspaceMember, Workspace.workspace_id == WorkspaceMember.workspace_id
        ).filter(
            WorkspaceMember.user_id == current_user,
            WorkspaceMember.is_active == True,
            Workspace.is_active == True
        ).order_by(
            WorkspaceMember.joined_at.desc()
        ).all()
    workspaces_data = []
    for workspace_name, workspace_description, workspace_id, role, joined_at in user_workspaces:
        # Get workspace statistics
        workspaces_data.append({
            'name': workspace_name,
            'role': capitalize_first_letter(role.name),
            'joined_at': joined_at,
            'description': workspace_description,
            'workspace_id': workspace_id
        })
    return workspaces_data


def capitalize_first_letter(text):
    return text.capitalize() if text else ''