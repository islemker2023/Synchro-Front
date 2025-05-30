import logging
import traceback
from datetime import datetime

from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify, session
from sqlalchemy.orm import joinedload

from Package import Workspace, db_session, app
from Package.condition_login import admin_required, login_required
from Package.forms import CreateObjectiveForm, EditObjectiveForm, SubObjectiveForm
from Package.models import Teachers, Users, Objective, SubObjective, Priority
from Package.routes.common.utils import get_workspace_info

bp = Blueprint('admin_objectives', __name__, url_prefix='/<workspace_id>/admin')
routes_logger = logging.getLogger('routes/admin')

@bp.route('/objectives')
@login_required
@admin_required
def admin_objectives(workspace_id):
    """Display objectives dashboard for admin"""
    try:
        workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()

        # Initialize create form
        create_form = CreateObjectiveForm(workspace_id)


        teachers = db_session.query(Teachers).filter(
            Teachers.workspace_id == workspace_id
        ).options(joinedload(Teachers.user)).all()

            # Optional: sanity check

        # Get all objectives with eager loading
        objectives = db_session.query(Objective).filter(
            Objective.workspace_id == workspace_id,
            Objective.is_active == True
        ).options(
            joinedload(Objective.teacher).joinedload(Teachers.user),
            joinedload(Objective.sub_objectives),
            joinedload(Objective.creator)
        ).order_by(Objective.created_at.desc()).all()

        objectives_data = []
        for objective in objectives:
            obj_data = {
                'name': objective.title,  # Note: model uses 'title', template expects 'name'
                'description': objective.description,
                'created_at': objective.created_at.strftime('%B %d, %Y'),  # Format as "January 15, 2024"
                'rate': f"{objective.get_completion_percentage()}%",  # Use the model's method
                'admin_name': objective.creator.full_name if objective.creator else "Unknown",  # Note: using full_name
                'teacher_name': objective.teacher.user.full_name if objective.teacher and objective.teacher.user else "Unassigned"
            }
            objectives_data.append(obj_data)

        # Get workspace objectives overview
        objectives_overview = workspace.get_objectives_overview()
        workspaces_info = get_workspace_info()
        return render_template('admin/objectives.html',
                               workspaces_info=workspaces_info,
                               workspace=workspace,
                               teachers=teachers,
                               objectives=objectives_data,
                               objectives_overview=objectives_overview,
                               create_form=create_form)
    except Exception as e:
        flash('Error loading workspaces. Please try again.', 'error')
        app.logger.error(f'Error in announcement: {str(e)}')
        traceback.print_exc()
        return "Error loading announcement", 500


@bp.route('/objectives/create', methods=['POST'])
@admin_required
@login_required
def create_objective(workspace_id):
    """Create a new objective for a teacher"""
    current_user = session.get('user_id')

    try:
        # Get form data from request
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        assigned_by = request.form.get('assigned_by', '').strip()
        due_date_str = request.form.get('due_date', '').strip()

        # Get tasks from form (they come as task_0, task_1, etc.)
        tasks = []
        task_index = 0
        while f'task_{task_index}' in request.form:
            task_title = request.form.get(f'task_{task_index}', '').strip()
            if task_title:  # Only add non-empty tasks
                tasks.append(task_title)
            task_index += 1

        # Basic validation
        if not title:
            flash('Objective title is required', 'error')
            return redirect(url_for('admin.admin_objectives.admin_objectives', workspace_id=workspace_id))

        if not assigned_by:
            flash('Assigned by field is required', 'error')
            return redirect(url_for('admin.admin_objectives.admin_objectives', workspace_id=workspace_id))

        # Parse due date
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid due date format', 'error')
                return redirect(url_for('admin.admin_objectives.admin_objectives', workspace_id=workspace_id))

        # Find teacher by user's full name
        teacher = db_session.query(Teachers).join(Users).filter(
            Users.full_name == assigned_by,
            Teachers.workspace_id == workspace_id
        ).first()

        if not teacher:
            # Alternative: try to find by email if that's what they're entering
            teacher = db_session.query.join(Users).filter(
                Users.email == assigned_by,
                Teachers.workspace_id == workspace_id
            ).first()

            if not teacher:
                flash(f'Teacher "{assigned_by}" not found in this workspace', 'error')
                return redirect(url_for('admin.admin_objectives.admin_objectives', workspace_id=workspace_id))

        # Get priority from form (optional)
        priority_str = request.form.get('priority', 'medium').lower()
        priority = Priority.MEDIUM  # default
        if priority_str == 'low':
            priority = Priority.LOW
        elif priority_str == 'high':
            priority = Priority.HIGH

        # Create objective
        objective = Objective(
            workspace_id=workspace_id,
            teacher_id=teacher.teacher_id,
            created_by=current_user,  # assuming current_user is already the user_id
            title=title,
            description=description,
            due_date=due_date,
            priority=priority
        )

        db_session.add(objective)
        db_session.flush()  # Get the objective ID

        # Create sub-objectives from tasks
        for i, task_title in enumerate(tasks):
            sub_objective = SubObjective(
                objective_id=objective.objective_id,
                title=task_title,
                description='',  # Empty description for now
                order_index=i
            )
            db_session.add(sub_objective)

        db_session.commit()
        flash('Objective created successfully!', 'success')

    except Exception as e:
        db_session.rollback()
        flash(f'Error creating objective: {str(e)}', 'error')
        routes_logger.error(f'Error creating objective: {str(e)}')

    return redirect(url_for('admin.admin_objectives.admin_objectives', workspace_id=workspace_id))




@bp.route('/objectives/<objective_id>/edit', methods=['GET', 'POST'])
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


@bp.route('/objectives/<objective_id>/delete', methods=['POST'])
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


@bp.route('/objectives/teacher/<teacher_id>')
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