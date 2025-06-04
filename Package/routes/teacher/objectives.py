import logging
import traceback

from flask import Blueprint, flash, redirect, url_for, render_template, jsonify, session
from sqlalchemy.orm import joinedload

from Package import db_session, app
from Package.condition_login import login_required, teacher_required
from Package.models import Teachers, Users, Objective, Workspace, SubObjective

bp = Blueprint('objectives', __name__, url_prefix='/<workspace_id>/teacher')
routes_logger = logging.getLogger('routes/teacher')

@bp.route('/objectives')
@teacher_required
@login_required
def teacher_objectives(workspace_id):
    """Display objectives for teachers"""
    try:
        current_user = session.get('user_id')
        # Check if user is a teacher in this workspace
        teacher = (
            db_session.query(Teachers)
            .join(Teachers.user)  # Assuming a relationship: Teachers.user → Users
            .filter(
                Teachers.workspace_id == workspace_id,
                Users.user_id == current_user
            )
            .first()
        )

        if not teacher:
            flash('You are not authorized to view objectives in this workspace.', 'error')
            return redirect(url_for('teacher.dashboard.teacher_dashboard', workspace_id=workspace_id))

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

        workspace = db_session.query(Workspace).get(workspace_id)

        return render_template('teacher/objectives.html',
                               workspace=workspace,
                               objectives=objectives,
                               objectives_summary=objectives_summary,
                               teacher=teacher)
    except Exception as e:
        flash('Error loading workspaces. Please try again.', 'error')
        app.logger.error(f'Error in Objective: {str(e)}')
        traceback.print_exc()
        return "Error loading Objective", 500


@bp.route('/objectives/<objective_id>/sub-objective/<sub_objective_id>/toggle', methods=['POST'])
@teacher_required
@login_required
def toggle_sub_objective(workspace_id, objective_id, sub_objective_id):
    """Toggle completion status of a sub-objective"""
    try:
        current_user = session.get('user_id')
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

@bp.route('/objectives/<objective_id>/details')
@teacher_required
@login_required
def get_objective_details(workspace_id, objective_id):
    """Get detailed information about a specific objective"""
    try:
        current_user = session.get('user_id')
        # Verify teacher access
        teacher = Teachers.query.join(Users).filter(
            Teachers.workspace_id == workspace_id,
            Users.user_id == current_user.user_id
        ).first()

        if not teacher:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403

        # Get objective with sub-objectives
        objective = db_session.query(Objective).filter(
            Objective.objective_id == objective_id,
            Objective.teacher_id == teacher.teacher_id,
            Objective.workspace_id == workspace_id,
            Objective.is_active == True
        ).options(
            joinedload(Objective.sub_objectives.and_(SubObjective.is_active == True))
        ).first()

        if not objective:
            return jsonify({'success': False, 'message': 'Objective not found'}), 404

        return jsonify({
            'success': True,
            'objective': {
                'id': str(objective.objective_id),
                'title': objective.title,
                'description': objective.description,
                'due_date': objective.due_date.isoformat() if objective.due_date else None,
                'completion_percentage': objective.get_completion_percentage(),
                'status': objective.get_status(),
                'is_overdue': objective.is_overdue(),
                'sub_objectives': [{
                    'id': str(sub.sub_objective_id),
                    'title': sub.title,
                    'description': sub.description,
                    'is_completed': sub.is_completed,
                    'completed_at': sub.completed_at.isoformat() if sub.completed_at else None,
                    'order_index': sub.order_index
                } for sub in sorted(objective.sub_objectives, key=lambda x: x.order_index)]
            }
        })

    except Exception as e:
        routes_logger.error(f"Error getting objective details: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred'}), 500