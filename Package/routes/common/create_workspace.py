import logging
from flask import Blueprint, request, flash, render_template, redirect, url_for, jsonify, session
from Package import db_session, Workspace, app
from Package.models import WorkspaceMember, WorkspaceRole, Admins
from Package.condition_login import login_required, admin_required

bp = Blueprint('create_workspace', __name__)
common_logger = logging.getLogger('routes/common')

@bp.route('/create_workspace', methods=['POST'])
@login_required
def create_workspace():
    """Handle workspace creation form submission"""
    try:
        current_user = session.get('user_id')
        # Get form data
        workspace_name = request.form.get('workspace_name')
        workspace_description = request.form.get('workspace_description')

        # Validation
        if not workspace_name:
            flash('Workspace name is required!', 'error')
            return render_template('create_workspace.html')

        if len(workspace_name) > 100:
            flash('Workspace name must not exceed 100 characters!', 'error')
            return render_template('create_workspace.html')

        # Check if workspace name already exists for this user
        existing_workspace = db_session.query(Workspace).filter(
            Workspace.name == workspace_name,
            Workspace.created_by == current_user,
            Workspace.is_active == True
        ).first()

        if existing_workspace:
            flash('You already have a workspace with this name!', 'error')
            return render_template('create_workspace.html')

        # Create the workspace
        new_workspace = Workspace(
            name=workspace_name,
            description=workspace_description,
            created_by=current_user,
            is_active=True
        )

        db_session.add(new_workspace)
        db_session.flush()  # To get the workspace_id

        # Add the creator as admin member
        admin_membership = WorkspaceMember(
            workspace_id=new_workspace.workspace_id,
            user_id=current_user,
            role=WorkspaceRole.ADMIN,
            is_active=True
        )

        db_session.add(admin_membership)

        # Optional: Create admin record in Admins table
        admin_record = Admins(
            user_id=current_user,
            workspace_id=new_workspace.workspace_id
        )

        db_session.add(admin_record)

        # Commit all changes
        db_session.commit()

        flash(f'Workspace "{workspace_name}" created successfully!', 'success')

        # Redirect to admin dashboard (adjust the blueprint name as needed)
        return redirect(url_for('admin.admin_dashboard.admin_dashboard', workspace_id=new_workspace.workspace_id))
    except Exception as e:
        db_session.rollback()
        flash('An error occurred while creating the workspace. Please try again.', 'error')
        app.logger.error(f'Error creating workspace: {str(e)}')
        return redirect(url_for('common.select_workspace.select_workspace'))