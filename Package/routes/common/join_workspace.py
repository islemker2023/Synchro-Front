import logging
from datetime import datetime

from flask import request, render_template, flash, redirect, url_for, Blueprint, session

from Package import db_session
from Package.forms import JoinWorkspaceForm, CreateWorkspaceForm
from Package.models import WorkspaceInvitation, WorkspaceMember, Workspace, Users, WorkspaceRole, Admins, Teachers, \
    Delegates
from Package.condition_login import login_required

bp = Blueprint('join_workspace', __name__)
common_logger = logging.getLogger('routes/common')


@bp.route('/join_workspace', methods=['POST'])
@login_required
def join_workspace():
    try:
        invitation_code = request.form.get('invite_code')
        current_user = session.get('user_id')

        if not invitation_code:
            flash('Invitation code is required', 'error')
            return redirect(url_for('common.select_workspace.select_workspace'))

        # Fetch user email string (not tuple)
        email_row = db_session.query(Users.email).filter(Users.user_id == current_user).first()
        if not email_row:
            flash('User email not found', 'error')
            return redirect(url_for('common.select_workspace.select_workspace'))
        email = email_row[0]  # extract string from tuple

        # Query full WorkspaceInvitation object (not just two fields)
        invitation = db_session.query(WorkspaceInvitation).filter(
            WorkspaceInvitation.email == email,
            WorkspaceInvitation.invitation_code == invitation_code
        ).first()

        if not invitation:
            flash('You have no access to this invitation code', 'error')
            return redirect(url_for('common.select_workspace.select_workspace'))

        # Make sure 'is_valid()' method exists in your WorkspaceInvitation model!
        if not invitation.is_valid():
            if invitation.is_used:
                flash('This invitation has already been used', 'error')
            else:
                flash('This invitation has expired', 'error')
            return redirect(url_for('common.select_workspace.select_workspace'))

        # Check if user is already a member
        existing_member = db_session.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == invitation.workspace_id,
            WorkspaceMember.user_id == current_user,
            WorkspaceMember.is_active == True
        ).first()

        if existing_member:
            flash('You are already a member of this workspace', 'warning')
            return redirect(url_for('common.select_workspace.select_workspace'))

        # Create new membership
        membership = WorkspaceMember(
            workspace_id=invitation.workspace_id,
            user_id=current_user,
            role=invitation.role
        )
        db_session.add(membership)

        # Add user to appropriate role-specific table based on their role
        if invitation.role == WorkspaceRole.ADMIN:
            # Check if admin record already exists
            existing_admin = db_session.query(Admins).filter(
                Admins.user_id == current_user,
                Admins.workspace_id == invitation.workspace_id
            ).first()

            if not existing_admin:
                admin = Admins(
                    user_id=current_user,
                    workspace_id=invitation.workspace_id
                )
                db_session.add(admin)

        elif invitation.role == WorkspaceRole.TEACHER:
            # Check if teacher record already exists
            existing_teacher = db_session.query(Teachers).filter(
                Teachers.user_id == current_user,
                Teachers.workspace_id == invitation.workspace_id
            ).first()

            if not existing_teacher:
                teacher = Teachers(
                    user_id=current_user,
                    workspace_id=invitation.workspace_id,
                    department=None,  # Can be updated later by the user
                    specialization=None  # Can be updated later by the user
                )
                db_session.add(teacher)

        elif invitation.role == WorkspaceRole.DELEGATE:
            # Check if delegate record already exists
            existing_delegate = db_session.query(Delegates).filter(
                Delegates.user_id == current_user,
                Delegates.workspace_id == invitation.workspace_id
            ).first()

            if not existing_delegate:
                delegate = Delegates(
                    user_id=current_user,
                    workspace_id=invitation.workspace_id
                )
                db_session.add(delegate)

        # Note: MEMBER role doesn't need a separate table entry as it's handled by WorkspaceMember

        # Mark invitation as used
        invitation.is_used = True
        invitation.used_at = datetime.utcnow()
        invitation.used_by = current_user

        # Commit all changes
        db_session.commit()

        workspace = db_session.query(Workspace).get(invitation.workspace_id)
        flash(f'Successfully joined workspace: {workspace.name}', 'success')
        return redirect(url_for('common.select_workspace.select_workspace'))

    except Exception as e:
        db_session.rollback()
        flash(f'Error joining workspace: {str(e)}', 'error')
        return redirect(url_for('common.select_workspace.select_workspace'))