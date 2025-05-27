from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from Package import db_session
# Assuming you have these imports from your existing code
from Package.models import Users, Workspace, WorkspaceMember, WorkspaceInvitation,WorkspaceRole

from Package.condition_login import admin_required  # Your existing decorator

bp = Blueprint('workspace_members', __name__)


@bp.route('/<workspace_id>/admin/manage_members')
@admin_required
@login_required
def manage_members(workspace_id):
    """Display the member management page"""
    workspace = Workspace.query.get_or_404(workspace_id)

    # Get current members
    members = db_session.query(WorkspaceMember, Users).join(
        Users, WorkspaceMember.user_id == Users.user_id
    ).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.is_active == True
    ).all()

    # Get pending invitations
    pending_invitations = WorkspaceInvitation.query.filter(
        WorkspaceInvitation.workspace_id == workspace_id,
        WorkspaceInvitation.is_used == False,
        WorkspaceInvitation.expires_at > datetime.utcnow()
    ).all()

    return render_template('admin/manage_members.html',
                           workspace=workspace,
                           members=members,
                           pending_invitations=pending_invitations,
                           workspace_roles=WorkspaceRole)


@bp.route('/<workspace_id>/admin/invite_member', methods=['POST'])
@admin_required
@login_required
def invite_member(workspace_id):
    """Invite a new member to the workspace"""
    try:
        email = request.form.get('email', '').strip().lower()
        role = request.form.get('role', WorkspaceRole.MEMBER.value)

        if not email:
            flash('Email is required', 'error')
            return redirect(url_for('workspace_members.manage_members', workspace_id=workspace_id))

        # Validate role
        try:
            role_enum = WorkspaceRole(role)
        except ValueError:
            flash('Invalid role selected', 'error')
            return redirect(url_for('workspace_members.manage_members', workspace_id=workspace_id))

        # Check if workspace exists
        workspace = Workspace.query.get_or_404(workspace_id)

        # Check if user is already a member
        existing_member = db_session.query(WorkspaceMember).join(Users).filter(
            WorkspaceMember.workspace_id == workspace_id,
            Users.email == email,
            WorkspaceMember.is_active == True
        ).first()

        if existing_member:
            flash('User is already a member of this workspace', 'error')
            return redirect(url_for('workspace_members.manage_members', workspace_id=workspace_id))

        # Check if there's already a pending invitation
        existing_invitation = WorkspaceInvitation.query.filter(
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.email == email,
            WorkspaceInvitation.is_used == False,
            WorkspaceInvitation.expires_at > datetime.utcnow()
        ).first()

        if existing_invitation:
            flash('An invitation has already been sent to this email', 'warning')
            return redirect(url_for('workspace_members.manage_members', workspace_id=workspace_id))

        # Create new invitation
        invitation = WorkspaceInvitation.create_invitation(
            workspace_id=workspace_id,
            email=email,
            invited_by_user_id=current_user.user_id,
            role=role_enum
        )

        db_session.add(invitation)
        db_session.commit()

        # Send email invitation
        if send_invitation_email(email, invitation.invitation_code, workspace.name, current_user.full_name):
            flash(f'Invitation sent successfully to {email}', 'success')
        else:
            flash(f'Invitation created but failed to send email to {email}. Code: {invitation.invitation_code}',
                  'warning')

        return redirect(url_for('workspace_members.manage_members', workspace_id=workspace_id))

    except Exception as e:
        db_session.rollback()
        flash(f'Error sending invitation: {str(e)}', 'error')
        return redirect(url_for('workspace_members.manage_members', workspace_id=workspace_id))



@bp.route('/<workspace_id>/admin/cancel_invitation/<invitation_id>', methods=['POST'])
@admin_required
@login_required
def cancel_invitation(workspace_id, invitation_id):
    """Cancel a pending invitation"""
    try:
        invitation = WorkspaceInvitation.query.filter(
            WorkspaceInvitation.invitation_id == invitation_id,
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.is_used == False
        ).first_or_404()

        db_session.delete(invitation)
        db_session.commit()

        flash('Invitation cancelled successfully', 'success')

    except Exception as e:
        db_session.rollback()
        flash(f'Error cancelling invitation: {str(e)}', 'error')

    return redirect(url_for('workspace_members.manage_members', workspace_id=workspace_id))


@bp.route('/<workspace_id>/admin/remove_member/<member_id>', methods=['POST'])
@admin_required
@login_required
def remove_member(workspace_id, member_id):
    """Remove a member from the workspace"""
    try:
        member = WorkspaceMember.query.filter(
            WorkspaceMember.id == member_id,
            WorkspaceMember.workspace_id == workspace_id
        ).first_or_404()

        # Don't allow removing yourself or the workspace creator
        workspace = Workspace.query.get(workspace_id)
        if member.user_id == current_user.user_id:
            flash('You cannot remove yourself from the workspace', 'error')
        elif member.user_id == workspace.created_by:
            flash('Cannot remove the workspace creator', 'error')
        else:
            member.is_active = False
            db_session.commit()
            flash('Member removed successfully', 'success')

    except Exception as e:
        db_session.rollback()
        flash(f'Error removing member: {str(e)}', 'error')

    return redirect(url_for('workspace_members.manage_members', workspace_id=workspace_id))


@bp.route('/<workspace_id>/admin/edit_member/<member_id>', methods=['POST'])
@admin_required
@login_required
def edit_member_role(workspace_id, member_id):
    """Edit a member's role in the workspace"""
    try:
        member = WorkspaceMember.query.filter(
            WorkspaceMember.id == member_id,
            WorkspaceMember.workspace_id == workspace_id
        ).first_or_404()

        # Don't allow editing yourself or the workspace creator
        workspace = Workspace.query.get(workspace_id)
        if member.user_id == current_user.user_id:
            flash('You cannot edit your own role in the workspace', 'error')
        elif member.user_id == workspace.created_by:
            flash('Cannot edit the role of the workspace creator', 'error')
        else:
            # Get the new role from the form data
            new_role = request.form.get('role')

            # Validate the new role
            if new_role not in [role.value for role in WorkspaceRole]:
                flash('Invalid role selected', 'error')
                return redirect(url_for('workspace_members.manage_members', workspace_id=workspace_id))

            # Convert string to enum
            new_role_enum = WorkspaceRole(new_role)

            # Update the member's role
            member.role = new_role_enum

            db_session.commit()
            flash(f'Member role updated to {new_role_enum.value} successfully', 'success')

    except Exception as e:
        db_session.rollback()
        flash(f'Error updating member role: {str(e)}', 'error')

    return redirect(url_for('workspace_members.manage_members', workspace_id=workspace_id))


def send_invitation_email(email, invitation_code, workspace_name, inviter_name):

        # Create message
        msg = MIMEMultipart()
        msg['From'] = 'synchro.no.reply1@gmail.com'
        msg['To'] = email
        msg['Subject'] = f'Invitation to join {workspace_name}'

        # Email body
        body = f"""
        Hello,

        You have been invited by {inviter_name} to join the workspace "{workspace_name}".

        To join the workspace:
        1. Create an account or log in with the email: {email}
        2. Go to the "Join Workspace" page
        3. Enter your email and the invitation code: {invitation_code}

        This invitation will expire in 7 days.

        Best regards,
        El jem3iya Team
        """

        msg.attach(MIMEText(body, 'plain'))

        # Send email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login('synchro.no.reply1@gmail.com', 'toepioxwzufcbjme')
        server.send_message(msg)
        server.quit()

        return True

