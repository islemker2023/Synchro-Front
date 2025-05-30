

from flask import Blueprint, render_template, request, jsonify, session
from datetime import datetime, date, timedelta
from sqlalchemy import extract
from Package import db_session  # Import your db instance
from Package.models import Events, Users, Workspace  # Import your models
from Package.forms import CreateEventForm  # Import your form
from Package.condition_login import admin_required, teacher_required, login_required  # Import your admin decorator

# Assuming you have a blueprint for admin routes
bp = Blueprint('teacher', __name__, url_prefix='/teacher')


@bp.route('/<workspace_id>/teacher/calendar')
@teacher_required
@login_required
def admin_calendar():
    return render_template('teacher/calendar.html')


@bp.route('/<workspace_id>/teacher/calendar/events')
@teacher_required
@login_required
def get_events():
    """Get events for calendar - supports filtering by date, month, year"""
    try:
        # Get current user's workspace
        current_user = session.get('user_id')
        workspace_id = request.args.get('workspace_id')
        if not workspace_id:
            # Get user's first workspace or handle appropriately
            user_workspace = current_user.workspace_memberships[
                0].workspace_id if current_user.workspace_memberships else None
            if not user_workspace:
                return jsonify({'success': False, 'message': 'No workspace found'})
            workspace_id = user_workspace

        # Get query parameters
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)
        day = request.args.get('day', type=int)

        # Base query
        query = db_session.query(Events).filter(
            Events.workspace_id == workspace_id,
            Events.is_active == True
        ).join(Users, Events.created_by == Users.user_id)

        # Apply date filters
        if year and month and day:
            # Specific date
            target_date = date(year, month, day)
            query = query.filter(Events.date == target_date)
        elif year and month:
            # Specific month
            query = query.filter(
                extract('year', Events.date) == year,
                extract('month', Events.date) == month
            )
        elif year:
            # Specific year
            query = query.filter(extract('year', Events.date) == year)

        events = query.order_by(Events.date, Events.time).all()

        # Format events for JSON response
        events_data = []
        for event in events:
            events_data.append({
                'id': str(event.events_id),
                'title': event.title,
                'description': event.description,
                'date': event.date.strftime('%Y-%m-%d'),
                'time': event.time.strftime('%H:%M'),
                'created_by': event.creator.full_name,
                'creator_id': str(event.created_by),
                'created_at': event.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })

        return jsonify({
            'success': True,
            'events': events_data,
            'count': len(events_data)
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/<workspace_id>/teacher/calendar/events/create', methods=['POST'])
@teacher_required
@login_required
def create_event():
    """Create a new event"""
    try:
        form = CreateEventForm()

        if form.validate_on_submit():
            current_user = session.get('user_id')
            # Get current user's workspace
            workspace_id = request.form.get('workspace_id')
            if not workspace_id:
                user_workspace = current_user.workspace_memberships[
                    0].workspace_id if current_user.workspace_memberships else None
                if not user_workspace:
                    return jsonify({'success': False, 'message': 'No workspace found'})
                workspace_id = user_workspace

            # Combine date and time
            event_datetime = datetime.combine(form.event_date.data, form.event_time.data)

            # Create new event
            new_event = Events(
                title=form.title.data,
                description=form.description.data,
                date=form.event_date.data,
                time=event_datetime,
                created_by=current_user.user_id,
                workspace_id=workspace_id
            )

            db_session.add(new_event)
            db_session.commit()

            return jsonify({
                'success': True,
                'message': 'Event created successfully',
                'event': {
                    'id': str(new_event.events_id),
                    'title': new_event.title,
                    'description': new_event.description,
                    'date': new_event.date.strftime('%Y-%m-%d'),
                    'time': new_event.time.strftime('%H:%M'),
                    'created_by': current_user.full_name
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Form validation failed',
                'errors': form.errors
            })

    except Exception as e:
        db_session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/<workspace_id>/teacher/calendar/events/<event_id>', methods=['DELETE'])
@teacher_required
@login_required
def delete_event(event_id, workspace_id):
    """Delete an event (soft delete)"""
    try:
        event = Events.query.filter_by(events_id=event_id, is_active=True).first()
        current_user = session.get('user_id')
        if not event:
            return jsonify({'success': False, 'message': 'Event not found'})

        # Check if user can delete (creator or admin)
        if event.created_by != current_user.user_id:
            # Check if user is admin of the workspace
            user_role = current_user.get_workspace_role(event.workspace_id)
            if user_role != 'ADMIN':
                return jsonify({'success': False, 'message': 'Permission denied'})

        # Soft delete
        event.is_active = False
        db_session.commit()

        return jsonify({'success': True, 'message': 'Event deleted successfully'})

    except Exception as e:
        db_session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/<workspace_id>/teacher/calendar/events/<event_id>', methods=['PUT'])
@teacher_required
@login_required
def update_event(event_id):
    """Update an event"""
    try:
        event = Events.query.filter_by(events_id=event_id, is_active=True).first()

        if not event:
            return jsonify({'success': False, 'message': 'Event not found'})
        current_user = session.get('user_id')
        # Check if user can edit (creator or admin)
        if event.created_by != current_user.user_id:
            user_role = current_user.get_workspace_role(event.workspace_id)
            if user_role != 'ADMIN':
                return jsonify({'success': False, 'message': 'Permission denied'})

        # Get JSON data
        data = request.get_json()

        # Update fields
        if 'title' in data:
            event.title = data['title']
        if 'description' in data:
            event.description = data['description']
        if 'date' in data:
            event.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        if 'time' in data:
            time_obj = datetime.strptime(data['time'], '%H:%M').time()
            event.time = datetime.combine(event.date, time_obj)

        db_session.commit()

        return jsonify({
            'success': True,
            'message': 'Event updated successfully',
            'event': {
                'id': str(event.events_id),
                'title': event.title,
                'description': event.description,
                'date': event.date.strftime('%Y-%m-%d'),
                'time': event.time.strftime('%H:%M'),
                'created_by': event.creator.full_name
            }
        })

    except Exception as e:
        db_session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/<workspace_id>/teacher/calendar/stats')
@teacher_required
@login_required
def calendar_stats():
    """Get calendar statistics"""
    try:
        current_user = session.get('user_id')
        # Get current user's workspace
        workspace_id = request.args.get('workspace_id')
        if not workspace_id:
            user_workspace = current_user.workspace_memberships[
                0].workspace_id if current_user.workspace_memberships else None
            if not user_workspace:
                return jsonify({'success': False, 'message': 'No workspace found'})
            workspace_id = user_workspace

        # Get current month's events
        current_date = datetime.now()
        start_of_month = current_date.replace(day=1)
        end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        # Total events this month
        total_events = Events.query.filter(
            Events.workspace_id == workspace_id,
            Events.is_active == True,
            Events.date >= start_of_month.date(),
            Events.date <= end_of_month.date()
        ).count()

        # Events by creator role
        teacher_events = db_session.query(Events).join(Users).join(
            current_user.workspace_memberships
        ).filter(
            Events.workspace_id == workspace_id,
            Events.is_active == True,
            Events.date >= start_of_month.date(),
            Events.date <= end_of_month.date()
        ).count()  # This would need more complex join logic

        # Upcoming events (next 7 days)
        upcoming_events = Events.query.filter(
            Events.workspace_id == workspace_id,
            Events.is_active == True,
            Events.date >= current_date.date(),
            Events.date <= (current_date + timedelta(days=7)).date()
        ).order_by(Events.date, Events.time).limit(5).all()

        upcoming_events_data = []
        for event in upcoming_events:
            upcoming_events_data.append({
                'title': event.title,
                'date': event.date.strftime('%Y-%m-%d'),
                'time': event.time.strftime('%H:%M'),
                'created_by': event.creator.full_name
            })

        return jsonify({
            'success': True,
            'stats': {
                'total_events': total_events,
                'teacher_events': 0,  # You can implement proper role-based counting
                'delegate_events': 0,  # You can implement proper role-based counting
                'upcoming_events': upcoming_events_data
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

