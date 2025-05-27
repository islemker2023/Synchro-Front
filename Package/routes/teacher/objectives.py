import logging

from flask import Blueprint, flash, redirect, url_for, render_template, jsonify
from flask_login import current_user
from sqlalchemy.orm import joinedload

from Package import db_session
from Package.condition_login import login_required, teacher_required
from Package.models import Teachers, Users, Objective, Workspace, SubObjective

bp = Blueprint('objectives', __name__, url_prefix='/routes/teacher')
routes_logger = logging.getLogger('routes/teacher')

@bp.route('/<workspace_id>/objectives')
@teacher_required
@login_required
def teacher_objectives(workspace_id):
    """Display objectives for teachers"""
    # Check if user is a teacher in this workspace
    teacher = Teachers.query.join(Users).filter(
        Teachers.workspace_id == workspace_id,
        Users.user_id == current_user.user_id
    ).first()

    if not teacher:
        flash('You are not authorized to view objectives in this workspace.', 'error')
        return redirect(url_for('main.workspace_dashboard', workspace_id=workspace_id))

    # Get teacher's objectives
    objectives = db_session.query(Objective).filter(
        Objective.teacher_id == teacher.teacher_id,
        Objective.is_active == True
    ).options(
        joinedload(Objective.sub_objectives),
        joinedload(Objective.creator)
    ).order_by(Objective.created_at.desc()).all()

    # Get objectives summary
    objectives_summary = teacher.get_objectives_summary()

    workspace = Workspace.query.get(workspace_id)

    return render_template('teacher/objectives.html',
                           workspace=workspace,
                           objectives=objectives,
                           objectives_summary=objectives_summary,
                           teacher=teacher)


@bp.route('/<workspace_id>/objectives/<objective_id>/sub-objective/<sub_objective_id>/toggle', methods=['POST'])
@teacher_required
@login_required
def toggle_sub_objective(workspace_id, objective_id, sub_objective_id):
    """Toggle completion status of a sub-objective"""
    try:
        # Verify user has access to this objective
        teacher = Teachers.query.join(Users).filter(
            Teachers.workspace_id == workspace_id,
            Users.user_id == current_user.user_id
        ).first()

        if not teacher:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403

        # Get the sub-objective
        sub_objective = db_session.query(SubObjective).join(Objective).filter(
            SubObjective.sub_objective_id == sub_objective_id,
            Objective.objective_id == objective_id,
            Objective.teacher_id == teacher.teacher_id,
            Objective.workspace_id == workspace_id
        ).first()

        if not sub_objective:
            return jsonify({'success': False, 'message': 'Sub-objective not found'}), 404

        # Toggle completion status
        if sub_objective.is_completed:
            sub_objective.mark_incomplete()
            message = 'Sub-objective marked as incomplete'
        else:
            sub_objective.mark_completed(current_user.user_id)
            message = 'Sub-objective marked as completed'

        db_session.commit()

        # Get updated completion percentage
        objective = sub_objective.objective
        completion_percentage = objective.get_completion_percentage()

        return jsonify({
            'success': True,
            'message': message,
            'is_completed': sub_objective.is_completed,
            'completion_percentage': completion_percentage,
            'objective_status': objective.get_status()
        })

    except Exception as e:
        db_session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500