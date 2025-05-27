import logging
from datetime import datetime

from flask import request, render_template, flash, redirect, url_for, Blueprint
from flask_login import current_user

from Package import db_session
from Package.models import WorkspaceInvitation, WorkspaceMember, Workspace
from Package.condition_login import login_required

bp = Blueprint('create_workspace', __name__, url_prefix='/routes/common')
common_logger = logging.getLogger('routes/common')


@bp.route('/join_workspace', methods=['GET', 'POST'])
@login_required
def join_workspace():
    """Join workspace using invitation code"""
    if request.method == 'GET':
        return render_template('join_workspace.html')

    try:
        email = request.form.get('email', '').strip().lower()
        invitation_code = request.form.get('invitation_code', '').strip().upper()

        if not email or not invitation_code:
            flash('Email and invitation code are required', 'error')
            return render_template('join_workspace.html')

        # Check if the email matches the logged-in user's email
        if email != current_user.email.lower():
            flash('The email must match your account email', 'error')
            return render_template('join_workspace.html')

        # Find the invitation
        invitation = WorkspaceInvitation.query.filter(
            WorkspaceInvitation.email == email,
            WorkspaceInvitation.invitation_code == invitation_code
        ).first()

        if not invitation:
            flash('Invalid invitation code or email', 'error')
            return render_template('join_workspace.html')

        if not invitation.is_valid():
            if invitation.is_used:
                flash('This invitation has already been used', 'error')
            else:
                flash('This invitation has expired', 'error')
            return render_template('join_workspace.html')

        # Check if user is already a member
        existing_member = WorkspaceMember.query.filter(
            WorkspaceMember.workspace_id == invitation.workspace_id,
            WorkspaceMember.user_id == current_user.user_id,
            WorkspaceMember.is_active == True
        ).first()

        if existing_member:
            flash('You are already a member of this workspace', 'warning')
            return redirect(url_for('main.dashboard'))  # Adjust route as needed

        # Create workspace membership
        membership = WorkspaceMember(
            workspace_id=invitation.workspace_id,
            user_id=current_user.user_id,
            role=invitation.role
        )

        # Mark invitation as used
        invitation.is_used = True
        invitation.used_at = datetime.utcnow()
        invitation.used_by = current_user.user_id

        db_session.add(membership)
        db_session.commit()

        workspace = Workspace.query.get(invitation.workspace_id)
        flash(f'Successfully joined workspace: {workspace.name}', 'success')
        return redirect(url_for('main.dashboard'))  # Adjust route as needed

    except Exception as e:
        db_session.rollback()
        flash(f'Error joining workspace: {str(e)}', 'error')
        return render_template('join_workspace.html')