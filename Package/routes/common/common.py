import logging
from flask import Blueprint, render_template, flash, request, redirect, url_for
from Package.condition_login import login_not_selected, login_required

bp = Blueprint('common', __name__)
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
    return render_template('common/privacy.html')

@bp.route('/getting_started')
def getting_started():
    return render_template('common/getting-started.html')

@bp.route('/support')
def support():
    return render_template('common/support.html')

@bp.route('/feature')
def feature():
    return render_template('common/features.html')

@bp.route('/documentation')
def documentation():
    return render_template('common/documentation.html')
