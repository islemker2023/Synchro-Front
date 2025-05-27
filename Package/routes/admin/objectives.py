import logging
from datetime import datetime

from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify
from flask_login import current_user
from sqlalchemy.orm import joinedload

from Package import Workspace, db_session
from Package.condition_login import admin_required, login_required
from Package.forms import CreateObjectiveForm, EditObjectiveForm, SubObjectiveForm
from Package.models import Teachers, Users, Objective, SubObjective

bp = Blueprint('files', __name__, url_prefix='/routes/admin')
routes_logger = logging.getLogger('routes/admin')

@bp.route('/<workspace_id>/admin/objectives')
@admin_required
@login_required
def admin_objectives(workspace_id):
    """Display objectives dashboard for admin"""
    workspace = Workspace.query.filter_by(workspace_id=workspace_id).first_or_404()

    # Initialize create form
    create_form = CreateObjectiveForm(workspace_id)

    # Get all teachers in the workspace
    teachers = db_session.query(Teachers).join(Users).filter(
        Teachers.workspace_id == workspace_id
    ).options(joinedload(Teachers.user)).all()

    # Get all objectives with eager loading
    objectives = db_session.query(Objective).filter(
        Objective.workspace_id == workspace_id,
        Objective.is_active == True
    ).options(
        joinedload(Objective.teacher).joinedload(Teachers.user),
        joinedload(Objective.sub_objectives),
        joinedload(Objective.creator)
    ).order_by(Objective.created_at.desc()).all()

    # Get workspace objectives overview
    objectives_overview = workspace.get_objectives_overview()

    return render_template('admin/objectives.html',
                           workspace=workspace,
                           teachers=teachers,
                           objectives=objectives,
                           objectives_overview=objectives_overview,
                           create_form=create_form)


@bp.route('/<workspace_id>/admin/objectives/create', methods=['POST'])
@admin_required
@login_required
def create_objective(workspace_id):
    """Create a new objective for a teacher using WTForms"""
    form = CreateObjectiveForm(workspace_id)

    if form.validate_on_submit():
        try:
            # Validate teacher exists in workspace
            teacher = Teachers.query.filter_by(
                teacher_id=form.teacher_id.data,
                workspace_id=workspace_id
            ).first()

            if not teacher:
                flash('Teacher not found in this workspace', 'error')
                return redirect(url_for('objectives.admin_objectives', workspace_id=workspace_id))

            # Create objective
            objective = Objective(
                workspace_id=workspace_id,
                teacher_id=form.teacher_id.data,
                created_by=current_user.user_id,
                title=form.title.data,
                description=form.description.data or '',
                due_date=form.due_date.data,
                priority=form.priority.data
            )

            db_session.add(objective)
            db_session.flush()  # Get the objective ID

            # Create sub-objectives
            for i, sub_form in enumerate(form.sub_objectives.data):
                if sub_form['title'].strip():  # Only create if title is provided
                    sub_objective = SubObjective(
                        objective_id=objective.objective_id,
                        title=sub_form['title'].strip(),
                        description=sub_form['description'].strip() if sub_form['description'] else '',
                        order_index=i
                    )
                    db_session.add(sub_objective)

            db_session.commit()
            flash('Objective created successfully!', 'success')

        except Exception as e:
            db_session.rollback()
            flash(f'Error creating objective: {str(e)}', 'error')
            routes_logger.error(f'Error creating objective: {str(e)}')
    else:
        # Form validation failed
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'error')

    return redirect(url_for('objectives.admin_objectives', workspace_id=workspace_id))


@bp.route('/<workspace_id>/admin/objectives/<objective_id>/edit', methods=['GET', 'POST'])
@admin_required
@login_required
def edit_objective(workspace_id, objective_id):
    """Edit an existing objective using WTForms"""
    objective = Objective.query.filter_by(
        objective_id=objective_id,
        workspace_id=workspace_id
    ).first_or_404()

    form = EditObjectiveForm()

    if request.method == 'GET':
        # Populate form with existing data
        form.title.data = objective.title
        form.description.data = objective.description
        form.due_date.data = objective.due_date
        form.priority.data = objective.priority.value if objective.priority else 'MEDIUM'

        # Populate sub-objectives
        form.sub_objectives.entries.clear()
        for sub_obj in sorted(objective.sub_objectives, key=lambda x: x.order_index):
            if sub_obj.is_active:
                sub_form = SubObjectiveForm()
                sub_form.title.data = sub_obj.title
                sub_form.description.data = sub_obj.description
                form.sub_objectives.append_entry(sub_form.data)

        return render_template('admin/edit_objective.html',
                               form=form,
                               objective=objective,
                               workspace_id=workspace_id)

    if form.validate_on_submit():
        try:
            # Update objective fields
            objective.title = form.title.data
            objective.description = form.description.data or ''
            objective.due_date = form.due_date.data
            objective.priority = form.priority.data
            objective.updated_at = datetime.utcnow()

            # Handle sub-objectives updates
            # First, mark all existing sub-objectives as inactive
            for sub_obj in objective.sub_objectives:
                sub_obj.is_active = False

            # Create new sub-objectives from form data
            for i, sub_form_data in enumerate(form.sub_objectives.data):
                if sub_form_data['title'].strip():
                    sub_objective = SubObjective(
                        objective_id=objective.objective_id,
                        title=sub_form_data['title'].strip(),
                        description=sub_form_data['description'].strip() if sub_form_data['description'] else '',
                        order_index=i
                    )
                    db_session.add(sub_objective)

            db_session.commit()
            flash('Objective updated successfully!', 'success')
            return redirect(url_for('objectives.admin_objectives', workspace_id=workspace_id))

        except Exception as e:
            db_session.rollback()
            flash(f'Error updating objective: {str(e)}', 'error')
            routes_logger.error(f'Error updating objective: {str(e)}')
    else:
        # Form validation failed
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'error')

    return render_template('admin/edit_objective.html',
                           form=form,
                           objective=objective,
                           workspace_id=workspace_id)


@bp.route('/<workspace_id>/admin/objectives/<objective_id>/delete', methods=['POST'])
@admin_required
@login_required
def delete_objective(workspace_id, objective_id):
    """Delete (deactivate) an objective"""
    try:
        objective = Objective.query.filter_by(
            objective_id=objective_id,
            workspace_id=workspace_id
        ).first_or_404()

        objective.is_active = False
        # Also deactivate all sub-objectives
        for sub_obj in objective.sub_objectives:
            sub_obj.is_active = False

        db_session.commit()
        flash('Objective deleted successfully!', 'success')

    except Exception as e:
        db_session.rollback()
        flash(f'Error deleting objective: {str(e)}', 'error')
        routes_logger.error(f'Error deleting objective: {str(e)}')

    return redirect(url_for('objectives.admin_objectives', workspace_id=workspace_id))


@bp.route('/<workspace_id>/admin/objectives/teacher/<teacher_id>')
@admin_required
@login_required
def get_teacher_objectives(workspace_id, teacher_id):
    """Get objectives for a specific teacher (AJAX endpoint)"""
    try:
        teacher = Teachers.query.filter_by(
            teacher_id=teacher_id,
            workspace_id=workspace_id
        ).first_or_404()

        objectives = db_session.query(Objective).filter(
            Objective.teacher_id == teacher_id,
            Objective.workspace_id == workspace_id,
            Objective.is_active == True
        ).options(joinedload(Objective.sub_objectives)).all()

        objectives_data = []
        for obj in objectives:
            objectives_data.append({
                'id': str(obj.objective_id),
                'title': obj.title,
                'description': obj.description,
                'due_date': obj.due_date.isoformat() if obj.due_date else None,
                'priority': obj.priority.value if obj.priority else 'medium',
                'completion_percentage': obj.get_completion_percentage(),
                'status': obj.get_status(),
                'sub_objectives': [
                    {
                        'id': str(sub.sub_objective_id),
                        'title': sub.title,
                        'description': sub.description,
                        'is_completed': sub.is_completed,
                        'completed_at': sub.completed_at.isoformat() if sub.completed_at else None
                    }
                    for sub in sorted(obj.sub_objectives, key=lambda x: x.order_index)
                    if sub.is_active
                ]
            })

        return jsonify({
            'success': True,
            'objectives': objectives_data,
            'teacher_name': teacher.user.full_name
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500