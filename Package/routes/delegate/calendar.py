import traceback

from flask import Blueprint, render_template, request, jsonify, flash
from datetime import datetime, date, timedelta, time
from sqlalchemy import extract
from Package import db_session, app
from Package.models import Events, Users, Workspace
from Package.condition_login import delegate_required, login_required
from Package.routes.common.utils import get_workspace_info

# Blueprint for delegate calendar routes
bp = Blueprint('calendar', __name__, url_prefix='/<workspace_id>/delegate')

# Additional blueprint for API compatibility with the JavaScript
api_bp = Blueprint('calendar_api', __name__, url_prefix='/api/admin/<workspace_id>/calendar')


# Main calendar page for delegates
@bp.route('/calendar')
@delegate_required
@login_required
def delegate_calendar(workspace_id):
    """Main calendar page for delegates"""
    try:
        print(f"Loading calendar for workspace: {workspace_id}")  # Debug print

        workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()
        if not workspace:
            print(f"Workspace not found: {workspace_id}")  # Debug print
            flash('Workspace not found.', 'error')
            return "Workspace not found", 404

        workspaces_info = get_workspace_info()
        return render_template('/delegate/calendar.html',
                               workspace=workspace,
                               workspaces_info=workspaces_info)
    except Exception as e:
        print(f"Error in delegate_calendar: {str(e)}")  # Debug print
        flash('Error loading calendar. Please try again.', 'error')
        app.logger.error(f'Error in delegate calendar: {str(e)}')
        traceback.print_exc()
        return "Error loading calendar", 500


# Shared function for getting events (used by both route patterns)
def get_events_data(workspace_id):
    """Shared function to get events for a workspace"""
    try:
        print(f"Getting events for workspace: {workspace_id}")
        workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()
        if not workspace:
            return {'success': False, 'message': 'Workspace not found'}, 404

        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)
        day = request.args.get('day', type=int)

        query = db_session.query(Events).filter(
            Events.workspace_id == workspace_id,
            Events.is_active == True
        )

        # Apply date filters if provided
        if year and month and day:
            query = query.filter(Events.date == date(year, month, day))
        elif year and month:
            query = query.filter(
                extract('year', Events.date) == year,
                extract('month', Events.date) == month
            )
        elif year:
            query = query.filter(extract('year', Events.date) == year)

        events = query.order_by(Events.date, Events.time).all()
        events_data = []

        for event in events:
            try:
                creator_name = 'Unknown'
                creator = db_session.query(Users).filter_by(user_id=event.created_by).first()
                if creator:
                    creator_name = creator.full_name

                # Format the start datetime properly for FullCalendar
                start_datetime = event.date.isoformat()
                if event.time and event.time.time() != time.min:
                    start_datetime = f"{event.date.isoformat()}T{event.time.strftime('%H:%M:%S')}"

                event_data = {
                    'id': str(event.events_id),
                    'title': event.title,
                    'description': event.description or '',
                    'date': event.date.strftime('%Y-%m-%d'),
                    'time': event.time.strftime('%H:%M:%S') if event.time else '00:00:00',
                    'start': start_datetime,
                    'type': getattr(event, 'type', 'General'),  # Add type field if it exists
                    'creator': creator_name,
                    'created_by': creator_name,
                    'creator_id': str(event.created_by),
                    'created_at': event.created_at.strftime('%Y-%m-%d %H:%M:%S') if event.created_at else ''
                }

                events_data.append(event_data)
                print(f"DEBUG: Processed event {event.events_id} with start: {start_datetime}")

            except Exception as format_error:
                app.logger.error(f'Error formatting event {event.events_id}: {str(format_error)}')
                print(f"Error processing event {event.events_id}: {format_error}")
                traceback.print_exc()
                continue

        return {
            'success': True,
            'events': events_data,
            'count': len(events_data)
        }, 200

    except Exception as e:
        print(f"Error getting events: {str(e)}")
        traceback.print_exc()
        return {
            'success': False,
            'message': 'Failed to load events',
            'error': str(e)
        }, 500


# Original delegate route for events
@bp.route('/calendar/events')
@delegate_required
@login_required
def get_events_delegate(workspace_id):
    """Get events via delegate route"""
    data, status_code = get_events_data(workspace_id)
    return jsonify(data), status_code


# API route for events (compatible with JavaScript expectations)
@api_bp.route('/events')
@delegate_required
@login_required
def get_events_api(workspace_id):
    """Get events via API route (compatible with JavaScript)"""
    data, status_code = get_events_data(workspace_id)
    return jsonify(data), status_code


# Calendar stats for both route patterns
def get_calendar_stats_data(workspace_id):
    """Shared function to get calendar statistics"""
    try:
        print(f"Getting stats for workspace: {workspace_id}")

        workspace = db_session.query(Workspace).filter_by(workspace_id=workspace_id).first()
        if not workspace:
            return {'success': False, 'message': 'Workspace not found'}, 404

        # Get current month's events
        current_date = datetime.now()
        start_of_month = current_date.replace(day=1)
        if current_date.month == 12:
            end_of_month = current_date.replace(year=current_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = current_date.replace(month=current_date.month + 1, day=1) - timedelta(days=1)

        # Total events this month
        total_events = db_session.query(Events).filter(
            Events.workspace_id == workspace_id,
            Events.is_active == True,
            Events.date >= start_of_month.date(),
            Events.date <= end_of_month.date()
        ).count()

        # Count events by type if type field exists
        teacher_events = 0
        delegate_events = 0
        try:
            if hasattr(Events, 'type'):
                teacher_events = db_session.query(Events).filter(
                    Events.workspace_id == workspace_id,
                    Events.is_active == True,
                    Events.type == 'Teacher',
                    Events.date >= start_of_month.date(),
                    Events.date <= end_of_month.date()
                ).count()

                delegate_events = db_session.query(Events).filter(
                    Events.workspace_id == workspace_id,
                    Events.is_active == True,
                    Events.type == 'Delegate',
                    Events.date >= start_of_month.date(),
                    Events.date <= end_of_month.date()
                ).count()
        except Exception as type_error:
            print(f"Warning: Could not count events by type: {type_error}")

        # Upcoming events (next 7 days)
        upcoming_date_limit = current_date + timedelta(days=7)
        upcoming_events_query = db_session.query(Events).filter(
            Events.workspace_id == workspace_id,
            Events.is_active == True,
            Events.date >= current_date.date(),
            Events.date <= upcoming_date_limit.date()
        ).order_by(Events.date, Events.time).limit(5)

        upcoming_events = upcoming_events_query.all()
        upcoming_events_data = []

        for event in upcoming_events:
            try:
                creator_name = 'Unknown'
                try:
                    creator = db_session.query(Users).filter_by(user_id=event.created_by).first()
                    if creator:
                        creator_name = creator.full_name
                except Exception:
                    pass

                upcoming_events_data.append({
                    'title': event.title,
                    'date': event.date.strftime('%Y-%m-%d'),
                    'time': event.time.strftime('%H:%M') if event.time else '00:00',
                    'created_by': creator_name
                })
            except Exception as e:
                print(f"Error formatting upcoming event: {e}")
                continue

        response = {
            'success': True,
            'stats': {
                'total_events': total_events,
                'teacher_events': teacher_events,
                'delegate_events': delegate_events,
                'upcoming_events': upcoming_events_data
            }
        }

        return response, 200

    except Exception as e:
        error_msg = f'Error getting calendar stats: {str(e)}'
        print(error_msg)
        app.logger.error(error_msg)
        traceback.print_exc()
        return {
            'success': False,
            'message': 'Failed to load statistics',
            'error': str(e)
        }, 500


# Original delegate route for stats
@bp.route('/calendar/stats')
@delegate_required
@login_required
def calendar_stats_delegate(workspace_id):
    """Get calendar statistics via delegate route"""
    data, status_code = get_calendar_stats_data(workspace_id)
    return jsonify(data), status_code


# API route for stats
@api_bp.route('/stats')
@delegate_required
@login_required
def calendar_stats_api(workspace_id):
    """Get calendar statistics via API route"""
    data, status_code = get_calendar_stats_data(workspace_id)
    return jsonify(data), status_code


# Test endpoints for both patterns
@bp.route('/calendar/test')
@delegate_required
@login_required
def test_endpoint_delegate(workspace_id):
    """Test endpoint via delegate route"""
    return jsonify({
        'success': True,
        'message': 'Delegate Calendar API is working!',
        'workspace_id': workspace_id,
        'route_type': 'delegate',
        'timestamp': datetime.now().isoformat()
    })


@api_bp.route('/test')
@delegate_required
@login_required
def test_endpoint_api(workspace_id):
    """Test endpoint via API route"""
    return jsonify({
        'success': True,
        'message': 'API Calendar route is working!',
        'workspace_id': workspace_id,
        'route_type': 'api',
        'timestamp': datetime.now().isoformat()
    })


# Debug route to show available endpoints
@bp.route('/calendar/debug/routes')
@delegate_required
@login_required
def debug_routes(workspace_id):
    """Debug endpoint to list all available routes"""
    try:
        routes = []
        for rule in app.url_map.iter_rules():
            if 'calendar' in rule.endpoint:
                routes.append({
                    'endpoint': rule.endpoint,
                    'methods': list(rule.methods),
                    'rule': str(rule)
                })

        return jsonify({
            'success': True,
            'workspace_id': workspace_id,
            'calendar_routes': routes,
            'available_endpoints': [
                f'/{workspace_id}/delegate/calendar',
                f'/{workspace_id}/delegate/calendar/events',
                f'/{workspace_id}/delegate/calendar/stats',
                f'/{workspace_id}/delegate/calendar/test',
                f'/api/admin/{workspace_id}/calendar/events',
                f'/api/admin/{workspace_id}/calendar/stats',
                f'/api/admin/{workspace_id}/calendar/test'
            ]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})