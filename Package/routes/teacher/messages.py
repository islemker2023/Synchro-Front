import logging
import traceback

from flask import Blueprint, request

from flask import render_template
from sqlalchemy import and_, or_

from Package import db_session, Workspace
from Package.condition_login import login_required, teacher_required
import base64
from flask import session, flash, redirect, url_for
from email.mime.text import MIMEText
import requests
from Package.models import Message, Users
from Package.routes.common.utils import get_workspace_info

bp = Blueprint('messages', __name__, url_prefix='/<workspace_id>/teacher')
routes_logger = logging.getLogger('routes')
@bp.route('/messages')
@login_required
@teacher_required
def teacher_messages(workspace_id):
    try:
        current_user_id = session.get('user_id')

        if not current_user_id:
            flash("User not authenticated", "danger")
            return redirect(url_for('auth.login.login'))

        token = session.get('google_token')
        if not token:
            flash("Google not authenticated", "danger")
            return redirect(url_for('auth.login.login'))

        workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()
        if not workspace:
            flash("Workspace not found.", "warning")
            return redirect(url_for('teacher.teacher_dashboard.teacher_dashboard'))
        current_user_email = db_session.query(Users.email).filter_by(
            user_id=current_user_id
        ).scalar()

        stored_messages = db_session.query(Message.message_content,
                                           Message.subject,
                                           Message.email).filter(
            or_(
                Message.user_id == current_user_id,
                and_(
                    Message.user_id != current_user_id,
                    Message.send_to == current_user_email
                )
            )
        ).all()

        # ✅ Step 7: Pass to template or return
        return render_template(
            'teacher/messages.html',
            workspace=workspace,
            workspace_info=get_workspace_info(),
            messages=stored_messages  # This is a list of dictionaries
        )

    except Exception as e:
        print(f"Error reading messages: {e}")
        flash("Unexpected error while loading messages", "danger")
        return redirect(url_for('teacher.teacher_dashboard.teacher_dashboard', workspace_id=workspace_id))

@bp.route('/api/send', methods=['POST'])
@login_required
def send_email(workspace_id):
    current_user_id = session.get('user_id')
    to_email = request.form.get('email')
    subject = request.form.get('Subject')
    message_body = request.form.get('Message')

    if not to_email or not subject or not message_body:
        flash("All fields are required.", "warning")
        return redirect(request.referrer)

    try:
        token = session.get('google_token')
        if not token:
            flash("You must authenticate with Google before sending emails.", "danger")
            return redirect(url_for('auth.login.login'))

        access_token = token['access_token']
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        message = MIMEText(message_body)
        message['to'] = to_email
        message['subject'] = subject
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        payload = {'raw': raw_message}

        response = requests.post(
            'https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
            headers=headers,
            json=payload
        )
        current_user_email = db_session.query(Users.email).filter_by(
            user_id=current_user_id
        ).scalar()
        if response.status_code == 200:
            flash('Message sent successfully!', 'success')
            message_id = response.json()['id']
            new_message = Message(
                workspace_id=workspace_id,
                subject=subject,
                message_content=message_body,
                user_id=current_user_id,
                email=current_user_email,
                send_to=to_email
            )
            db_session.add(new_message)
            db_session.commit()
            return redirect(url_for('teacher.messages.teacher_messages', workspace_id=workspace_id))
        else:
            flash(f'Failed to send message: {response.text}', 'danger')
            return redirect(request.referrer)

    except Exception as e:
        print(traceback.format_exc())  # Log the full traceback during development
        flash("An unexpected error occurred while sending the email.", "danger")
        return redirect(url_for('teacher.messages.teacher_messages', workspace_id=workspace_id))

