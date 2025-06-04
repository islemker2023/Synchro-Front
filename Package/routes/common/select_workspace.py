import logging
import traceback
from flask import Blueprint, render_template, flash, session
from Package import  app
from Package.forms import CreateWorkspaceForm
from Package.condition_login import login_required
from Package.routes.common.utils import get_workspace_info, capitalize_first_letter

bp = Blueprint('select_workspace', __name__)
common_logger = logging.getLogger('routes/common')

@bp.route('/select_workspace')
@login_required
def select_workspace():
    """Display user's workspaces with database query"""
    form = CreateWorkspaceForm()
    current_user = session.get('user_id')
    try:
        # Query all active workspace memberships for the current user
        user_workspaces=get_workspace_info()
        # Format the data for template
        return render_template('join-workspace.html',
                               workspace_data=user_workspaces,
                               form=form,
                               )
    except Exception as e:
        flash('Error loading workspaces. Please try again.', 'error')
        app.logger.error(f'Error in select_workspace: {str(e)}')
        traceback.print_exc()
        return render_template('join-workspace.html', workspaces_data=[])