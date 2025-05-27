import logging

from flask import Blueprint, render_template, flash, request, redirect, url_for
from flask_login import current_user

from Package import db_session, Workspace, app
from Package.models import WorkspaceMember, Courses, Assignments, Notices, WorkspaceRole, Admins
from Package.condition_login import login_not_selected, login_required

bp = Blueprint('common', __name__, url_prefix='/routes/common')
routes_logger = logging.getLogger('routes')

@bp.route('/')
@bp.route('/home')
@login_not_selected
def home():
    return render_template('home.html')

@bp.route('/about')
def about():
    return render_template('about.html')

@bp.route('/privacy_policy')
def privacy():
    return render_template('privacy.html')


