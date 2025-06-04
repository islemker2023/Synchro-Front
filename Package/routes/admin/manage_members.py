import traceback

from flask import Blueprint, render_template, request, flash, redirect, url_for,  session
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from Package import db_session, app
# Assuming you have these imports from your existing code
from Package.models import Users, Workspace, WorkspaceMember, WorkspaceInvitation,WorkspaceRole
from Package.forms import InviteForm

from Package.condition_login import admin_required, login_required  # Your existing decorator
from Package.routes.common.utils import get_workspace_info, capitalize_first_letter

bp = Blueprint('admin_manage_members', __name__, url_prefix='/<workspace_id>/admin')


@bp.route('/manage_members', methods=['GET','POST'])
@login_required
@admin_required
def manage_members(workspace_id):
    try:
        app.logger.debug(f"Accessing manage_members for workspace_id={workspace_id}")

        current_user_id = session.get('user_id')
        app.logger.debug(f"Current user ID from session: {current_user_id}")

        # Initialize form
        form = InviteForm()

        # Handle form submission
        if form.validate_on_submit() and request.method == 'POST':
            email = form.email.data
            role = form.role.data
            app.logger.debug(f"Form submitted with email={email}, role={role}")

            try:
                role_enum = WorkspaceRole(role)
                app.logger.debug(f"Role enum resolved: {role_enum}")
            except ValueError as ve:
                app.logger.error(f"Invalid role submitted: {role}")
                flash("Invalid role selected.", "error")
                return redirect(url_for('admin.admin_manage_members.manage_members', workspace_id=workspace_id))

            # Check workspace existence
            workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()
            app.logger.debug(f"Workspace found: {workspace.name}")

            # Check if user is already a member
            existing_member = db_session.query(WorkspaceMember).join(Users).filter(
                WorkspaceMember.workspace_id == workspace_id,
                Users.email == email,
                WorkspaceMember.is_active == True
            ).first()
            if existing_member:
                app.logger.warning("User is already a member of this workspace")
                flash('User is already a member of this workspace', 'error')
                return redirect(url_for('admin.admin_manage_members.manage_members', workspace_id=workspace_id))

            # Check if invitation already exists
            existing_invitation = db_session.query(WorkspaceInvitation).filter(
                WorkspaceInvitation.workspace_id == workspace_id,
                WorkspaceInvitation.email == email,
                WorkspaceInvitation.is_used == False,
                WorkspaceInvitation.expires_at > datetime.utcnow()
            ).first()
            if existing_invitation:
                app.logger.info("Pending invitation already exists")
                flash('An invitation has already been sent to this email', 'warning')
                return redirect(url_for('admin.admin_manage_members.manage_members', workspace_id=workspace_id))

            # Create and save new invitation
            invitation = WorkspaceInvitation.create_invitation(
                workspace_id=workspace_id,
                email=email,
                invited_by_user_id=current_user_id,
                role=role_enum
            )
            db_session.add(invitation)
            db_session.commit()
            app.logger.debug(f"Invitation created with code: {invitation.invitation_code}")

            # Get inviter info
            inviter = db_session.query(Users).filter_by(user_id=current_user_id).first()
            if not inviter:
                app.logger.error("Inviter not found")
                flash("Internal error: inviter not found", "error")
                return redirect(url_for('admin.admin_manage_members.manage_members', workspace_id=workspace_id))

            # Send invitation email
            if send_invitation_email(email, invitation.invitation_code, workspace.name, inviter.full_name):
                flash(f'Invitation sent successfully to {email}', 'success')
                app.logger.info(f"Invitation email sent to {email}")
            else:
                flash(f'Invitation created but failed to send email to {email}. Code: {invitation.invitation_code}',
                      'warning')
                app.logger.warning(f"Failed to send invitation email to {email}")

        # Query current active members
        members_query = db_session.query(WorkspaceMember, Users).join(
            Users, WorkspaceMember.user_id == Users.user_id
        ).filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.is_active == True
        ).all()
        app.logger.debug(f"Fetched {len(members_query)} active members")

        members = []
        for workspace_member, user in members_query:
            member = type('obj', (object,), {
                'full_name': user.full_name,
                'email': user.email,
                'role': capitalize_first_letter(workspace_member.role.value),
                'joined_at': workspace_member.joined_at.strftime('%B %d, %Y')
            })
            members.append(member)

        # Fetch pending invitations
        pending_invitations = db_session.query(WorkspaceInvitation).filter(
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.is_used == False,
            WorkspaceInvitation.expires_at > datetime.utcnow()
        ).all()
        app.logger.debug(f"Fetched {len(pending_invitations)} pending invitations")

        # Workspace context info
        workspaces_info = get_workspace_info()
        workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()

        return render_template('admin/manage_members.html',
                               form=form,
                               workspace=workspace,
                               workspaces_info=workspaces_info,
                               members=members,
                               pending_invitations=pending_invitations,
                               workspace_roles=WorkspaceRole)

    except Exception as e:
        app.logger.error(f'Exception in manage_members: {str(e)}')
        traceback.print_exc()
        flash('Error loading workspace. Please try again.', 'error')
        return "Error loading workspace", 500

@bp.route('/cancel_invitation/<invitation_id>', methods=['POST'])
@login_required
@admin_required
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

    return redirect(url_for('admin.admin_manage_members.manage_members', workspace_id=workspace_id))


@bp.route('/remove_member/<member_id>', methods=['POST'])
@admin_required
@login_required
def remove_member(workspace_id, member_id):
    """Remove a member from the workspace"""
    try:
        current_user_id=session.get('user_id')
        member = WorkspaceMember.query.filter(
            WorkspaceMember.id == member_id,
            WorkspaceMember.workspace_id == workspace_id
        ).first_or_404()

        # Don't allow removing yourself or the workspace creator
        workspace = Workspace.query.get(workspace_id)
        if member.user_id == current_user_id:
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

    return redirect(url_for('admin.admin_manage_members.manage_members', workspace_id=workspace_id))


@bp.route('/edit_member/<member_id>', methods=['POST'])
@login_required
@admin_required
def edit_member_role(workspace_id, member_id):
    """Edit a member's role in the workspace"""
    current_user_id = session.get('user_id')
    try:
        member = WorkspaceMember.query.filter(
            WorkspaceMember.id == member_id,
            WorkspaceMember.workspace_id == workspace_id
        ).first_or_404()

        # Don't allow editing yourself or the workspace creator
        workspace = Workspace.query.get(workspace_id)
        if member.user_id == current_user_id:
            flash('You cannot edit your own role in the workspace', 'error')
        elif member.user_id == workspace.created_by:
            flash('Cannot edit the role of the workspace creator', 'error')
        elif member.role =='ADMIN':
            flash('Cannot edit the role of an Admin', 'error')
        else:
            # Get the new role from the form data
            new_role = request.form.get('role')

            # Validate the new role
            if new_role not in [role.value for role in WorkspaceRole]:
                flash('Invalid role selected', 'error')
                return redirect(url_for('admin_manage_members.manage_members', workspace_id=workspace_id))

            # Convert string to enum
            new_role_enum = WorkspaceRole(new_role)

            # Update the member's role
            member.role = new_role_enum

            db_session.commit()
            flash(f'Member role updated to {new_role_enum.value} successfully', 'success')

    except Exception as e:
        db_session.rollback()
        flash(f'Error updating member role: {str(e)}', 'error')

    return redirect(url_for('admin.admin_manage_members.manage_members', workspace_id=workspace_id))


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