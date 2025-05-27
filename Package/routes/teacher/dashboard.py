


@bp.route('/teacher/dashboard')
@login_required
def teacher_dashboard():
    return render_template('/teacher/dashboard.html')