import logging

from flask import Blueprint, render_template

from Package.condition_login import login_required

bp = Blueprint('teacher', __name__, url_prefix='/routes')
routes_logger = logging.getLogger('routes')


@bp.route('/<workspace_id>/teacher/announcement')
@login_required
def teacher_announcement():
    return render_template('teacher/announcement.html' )

@bp.route('/<workspace_id>/teacher/dashboard')
@login_required
def teacher_dashboard():
    return render_template('/teacher/dashboard.html')


@bp.route('/<workspace_id>/teacher/objectives')
@login_required
def teacher_objectives():
    return render_template('/teacher/objectives.html')

@bp.route('/<workspace_id>/teacher/messages')
@login_required
def teacher_messages():
    return render_template('/teacher/messages.html')

@bp.route('/<workspace_id>/teacher/files')
@login_required
def teacher_files():
    return render_template('/teacher/files.html')

@bp.route('/<workspace_id>/teacher/calendar')
@login_required
def teacher_calendar():
    return render_template('/teacher/calendar.html')

@bp.route('/<workspace_id>/teacher/tasks')
@login_required
def teacher_tasks():
    return render_template('/teacher/tasks.html')


@bp.route('/<workspace_id>/teacher/profile')
@login_required
def teacher_profile():
    return render_template('teacher/profile.html')