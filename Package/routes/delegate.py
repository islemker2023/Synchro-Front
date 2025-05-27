import logging

from flask import Blueprint, render_template

from Package.condition_login import login_required

bp = Blueprint('delegate', __name__, url_prefix='/routes')
routes_logger = logging.getLogger('routes')


@bp.route('/delegate/announcement')
@login_required
def delegate_announcement():
    return render_template('delegate/announcement.html' )

@bp.route('/delegate/dashboard')
@login_required
def delegate_dashboard():
    return render_template('/delegate/dashboard.html')

@bp.route('/delegate/messages')
@login_required
def delegate_messages():
    return render_template('/delegate/messages.html')

@bp.route('/delegate/tasks')
@login_required
def delegate_tasks():
    return render_template('/delegate/tasks.html')

@bp.route('/delegate/files')
@login_required
def delegate_files():
    return render_template('/delegate/files.html')

@bp.route('/delegate/calendar')
@login_required
def delegate_calendar():
    return render_template('/delegate/calendar.html')

@bp.route('/delegate/profile')
@login_required
def delegate_profile():
    return render_template('delegate/profile.html')
