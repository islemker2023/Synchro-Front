import traceback
from datetime import datetime

from flask import Blueprint, render_template, flash, session, jsonify, request, redirect, url_for
from Package import db_session, app  # Import your db instance
from Package.models import Events, Users, Workspace, WorkspaceRole  # Import your models
from Package.condition_login import admin_required  # Import your admin decorator
from Package.routes.auth.utils import login_required
from Package.routes.common.utils import get_workspace_info

# Blueprint for admin calendar routes - matches JS API expectations
bp = Blueprint('admin_calendar', __name__, url_prefix='/<workspace_id>/admin')
# Additional blueprint for API routes that match the JS pattern
api_bp = Blueprint('admin_calendar_api', __name__, url_prefix='/api/admin/<workspace_id>/calendar')


# Helper function to get current user object
def get_current_user():
    user_id = session.get('user_id')
    if user_id:
        return db_session.query(Users).filter_by(user_id=user_id).first()
    return None


# Calendar page route (existing)
@bp.route('/calendar')
@login_required
@admin_required
def calendar_page(workspace_id):
    """Display the calendar page"""
    try:
        workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()
        if not workspace:
            flash('Workspace not found', 'error')
            return redirect(url_for('admin.admin_dashboard.dashboard'))

        # Get workspace info if you have that utility function
        workspace_info = get_workspace_info()

        return render_template('admin/calendar.html',
                               workspace=workspace_info,
                               workspace_id=workspace_id)
    except Exception as e:
        app.logger.error(f'Error loading calendar page: {str(e)}')
        flash('Error loading calendar', 'error')
        return redirect('/')


# API ROUTES - These match the JavaScript expectations
@api_bp.route('/events', methods=['GET'])
@login_required
@admin_required
def get_events_api(workspace_id):
    """Get all events for the workspace - API endpoint"""
    try:
        workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()
        if not workspace:
            return jsonify({'error': 'Workspace not found'}), 404

        events_query = db_session.query(Events).filter_by(
            workspace_id=workspace_id,
            is_active=True
        ).order_by(Events.date.asc())

        events_list = []
        for event in events_query:
            # Get the creator's role in the workspace
            creator_role = event.creator.get_workspace_role(workspace_id)
            event_type = "Teacher" if creator_role in [WorkspaceRole.TEACHER, WorkspaceRole.ADMIN] else "Delegate"

            events_list.append({
                'id': str(event.events_id),
                'title': event.title,
                'start': event.date.isoformat() if event.time.time() == datetime.min.time() else event.time.isoformat(),
                'type': event_type,
                'description': event.description or '',
                'creator': event.creator.full_name
            })

        return jsonify({'events': events_list})
    except Exception as e:
        app.logger.error(f'Error fetching events: {str(e)}')
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch events'}), 500


@api_bp.route('/events', methods=['POST'])
@login_required
@admin_required
def create_event_api(workspace_id):
    """Create a new event - API endpoint"""
    try:
        data = request.get_json()

        # Validate required fields
        if not data.get('title') or not data.get('date') or not data.get('type'):
            return jsonify({'error': 'Missing required fields'}), 400

        workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()
        if not workspace:
            return jsonify({'error': 'Workspace not found'}), 404

        # Parse date and time
        event_date = datetime.strptime(data['date'], '%Y-%m-%d').date()

        # Handle time - if provided, combine with date; otherwise use date only
        if data.get('time'):
            time_obj = datetime.strptime(data['time'], '%H:%M').time()
            event_datetime = datetime.combine(event_date, time_obj)
        else:
            # Use start of day for all-day events
            event_datetime = datetime.combine(event_date, datetime.min.time())

        # Get current user object properly
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'User not found'}), 401

        # Create new event
        new_event = Events(
            title=data['title'],
            created_by=current_user.user_id,
            workspace_id=workspace_id,
            date=event_date,
            time=event_datetime,
            description=data.get('description', '')
        )

        db_session.add(new_event)
        db_session.commit()

        # Get creator role for response
        creator_role = current_user.get_workspace_role(workspace_id)
        event_type = "Teacher" if creator_role in [WorkspaceRole.TEACHER, WorkspaceRole.ADMIN] else "Delegate"

        # Return the created event
        response_event = {
            'id': str(new_event.events_id),
            'title': new_event.title,
            'start': event_date.isoformat() if data.get('time') is None else event_datetime.isoformat(),
            'type': event_type,
            'description': new_event.description or '',
            'creator': current_user.full_name
        }

        return jsonify({'event': response_event}), 201

    except ValueError as e:
        return jsonify({'error': 'Invalid date or time format'}), 400
    except Exception as e:
        db_session.rollback()
        app.logger.error(f'Error creating event: {str(e)}')
        traceback.print_exc()
        return jsonify({'error': 'Failed to create event'}), 500


@api_bp.route('/events/<event_id>', methods=['PUT'])
@login_required
@admin_required
def update_event_api(workspace_id, event_id):
    """Update an existing event - API endpoint"""
    try:
        data = request.get_json()

        # Find the event
        event = db_session.query(Events).filter_by(
            events_id=event_id,
            workspace_id=workspace_id,
            is_active=True
        ).first()

        if not event:
            return jsonify({'error': 'Event not found'}), 404

        # Get current user object properly
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'User not found'}), 401

        # Check if user can edit this event (creator or admin)
        if event.created_by != current_user.user_id and not current_user.is_workspace_admin(workspace_id):
            return jsonify({'error': 'Permission denied'}), 403

        # Validate required fields
        if not data.get('title') or not data.get('date') or not data.get('type'):
            return jsonify({'error': 'Missing required fields'}), 400

        # Parse date and time
        event_date = datetime.strptime(data['date'], '%Y-%m-%d').date()

        if data.get('time'):
            time_obj = datetime.strptime(data['time'], '%H:%M').time()
            event_datetime = datetime.combine(event_date, time_obj)
        else:
            event_datetime = datetime.combine(event_date, datetime.min.time())

        # Update event
        event.title = data['title']
        event.date = event_date
        event.time = event_datetime
        event.description = data.get('description', '')

        db_session.commit()

        # Get creator role for response
        creator_role = event.creator.get_workspace_role(workspace_id)
        event_type = "Teacher" if creator_role in [WorkspaceRole.TEACHER, WorkspaceRole.ADMIN] else "Delegate"

        # Return updated event
        response_event = {
            'id': str(event.events_id),
            'title': event.title,
            'start': event_date.isoformat() if data.get('time') is None else event_datetime.isoformat(),
            'type': event_type,
            'description': event.description or '',
            'creator': event.creator.full_name
        }

        return jsonify({'event': response_event})

    except ValueError as e:
        return jsonify({'error': 'Invalid date or time format'}), 400
    except Exception as e:
        db_session.rollback()
        app.logger.error(f'Error updating event: {str(e)}')
        traceback.print_exc()
        return jsonify({'error': 'Failed to update event'}), 500


@api_bp.route('/events/<event_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_event_api(workspace_id, event_id):
    """Delete an event (soft delete) - API endpoint"""
    try:
        # Find the event
        event = db_session.query(Events).filter_by(
            events_id=event_id,
            workspace_id=workspace_id,
            is_active=True
        ).first()

        if not event:
            return jsonify({'error': 'Event not found'}), 404

        # Get current user object properly
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'User not found'}), 401

        # Check if user can delete this event (creator or admin)
        if event.created_by != current_user.user_id and not current_user.is_workspace_admin(workspace_id):
            return jsonify({'error': 'Permission denied'}), 403

        # Soft delete
        event.is_active = False
        db_session.commit()

        return jsonify({'message': 'Event deleted successfully'})

    except Exception as e:
        db_session.rollback()
        app.logger.error(f'Error deleting event: {str(e)}')
        traceback.print_exc()
        return jsonify({'error': 'Failed to delete event'}), 500


# LEGACY ROUTES - Keep these for backward compatibility if needed
@bp.route('/api/events', methods=['GET'])
@login_required
@admin_required
def get_events(workspace_id):
    """Get all events for the workspace - Legacy endpoint"""
    return get_events_api(workspace_id)


@bp.route('/api/events', methods=['POST'])
@login_required
@admin_required
def create_event(workspace_id):
    """Create a new event - Legacy endpoint"""
    return create_event_api(workspace_id)


@bp.route('/api/events/<event_id>', methods=['PUT'])
@login_required
@admin_required
def update_event(workspace_id, event_id):
    """Update an existing event - Legacy endpoint"""
    return update_event_api(workspace_id, event_id)


@bp.route('/api/events/<event_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_event(workspace_id, event_id):
    """Delete an event (soft delete) - Legacy endpoint"""
    return delete_event_api(workspace_id, event_id)