import base64
import logging
import traceback
from email.mime.text import MIMEText

import requests
from flask import Blueprint, session, render_template, flash, redirect, url_for, request
from sqlalchemy import or_

from Package import db_session
from Package.condition_login import delegate_required, login_required
from Package.models import WorkspaceMember, Workspace, Users, Message
from Package.routes.common.utils import get_workspace_info

bp = Blueprint('messages', __name__, url_prefix='/<workspace_id>/delegate')
routes_logger = logging.getLogger('routes/delegate')

@bp.route('/messages')
@delegate_required
@login_required
def delegate_messages(workspace_id):
    try:
        current_user_id = session.get('user_id')

        if not current_user_id:
            flash("User not authenticated", "danger")
            return redirect(url_for('auth.login.login'))

        # token = session.get('google_token')
        # if not token:
        #     flash("Google not authenticated", "danger")
        #     return redirect(url_for('auth.login.login'))

        workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()
        if not workspace:
            flash("Workspace not found.", "warning")
            return redirect(url_for('admin.admin_dashboard.admin_dashboard'))
        current_user_email = db_session.query(Users.email).filter_by(
            user_id=current_user_id
        ).scalar()

        stored_messages = db_session.query(Message.message_content,
                                           Message.subject,
                                           Message.email).filter(
            or_(
                Message.user_id == current_user_id,
                Message.send_to == current_user_email
            )
        ).all()

        return render_template(
            'delegate/messages.html',
            workspace=workspace,
            workspace_info=get_workspace_info(),
            messages=stored_messages  # This is a list of dictionaries
        )

    except Exception as e:
        print(f"Error reading messages: {e}")
        flash("Unexpected error while loading messages", "danger")
        return redirect(url_for('admin.admin_dashboard.admin_dashboard', workspace_id=workspace_id))


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

    recepient_id = db_session.query(Users.user_id).filter_by(
        email=to_email
    ).scalar()
    recepient = db_session.query(WorkspaceMember).filter_by(
        workspace_id=workspace_id,
        user_id=recepient_id,
    ).first()
    if not recepient:
        flash("the recepient is not a member", "danger")
        return redirect(url_for('admin.messages.admin_messages', workspace_id=workspace_id))
    else:
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
            current_user_name = db_session.query(Users.full_name).filter_by(
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
                    send_to=to_email,
                    sender_name=current_user_name
                )
                db_session.add(new_message)
                db_session.commit()
                return redirect(url_for('admin.messages.admin_messages', workspace_id=workspace_id))
            else:
                flash(f'Failed to send message: {response.text}', 'danger')
                return redirect(request.referrer)

        except Exception as e:
            print(traceback.format_exc())  # Log the full traceback during development
            flash("An unexpected error occurred while sending the email.", "danger")
            return redirect(url_for('admin.messages.admin_messages', workspace_id=workspace_id))