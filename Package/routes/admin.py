import logging

from flask import Blueprint, render_template

from Package.auth.utils import role_required
from Package.condition_login import login_required, admin_required

bp = Blueprint('admin', __name__, url_prefix='/routes')
routes_logger = logging.getLogger('routes')


@bp.route('/admin/dashboard')
@admin_required
@login_required
def admin_dashboard():
    return render_template('/admin/dashboard.html')


@bp.route('/admin/messages')
@admin_required
@login_required
def admin_messages():
    return render_template('/admin/messages.html')

@bp.route('/admin/calendar')
@admin_required
@login_required
def admin_calendar():
    return render_template('/admin/calendar.html')

@bp.route('/admin/profile')
@admin_required
@login_required
def admin_profile():



    return render_template('admin/profile.html')