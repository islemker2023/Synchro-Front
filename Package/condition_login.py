from functools import wraps
from flask import session, url_for, redirect, abort, request, g
from flask_login import current_user

from Package.models import WorkspaceRole


#@login_required configuration (definition)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'connected' not in session:# Check if user is logged in
            return redirect(url_for('auth.login.login'))  # Redirect to login if not
        return f(*args, **kwargs)  # Otherwise continue to the route
    return decorated_function
def login_not_selected(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'connected' in session:
            return redirect(url_for('select_workspace'))
        return f(*args, **kwargs)
    return decorated_function


def workspace_role_required(allowed_roles=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):

            # Get workspace_id from URL parameters
            workspace_id = kwargs.get('workspace_id')
            if not workspace_id:
                abort(400, "Workspace ID not found in URL")

            # Get user's role in this workspace
            user_role = current_user.get_workspace_role(workspace_id)

            if not user_role:
                abort(403, "You are not a member of this workspace")

            # Auto-detect required role from route path if not specified
            if allowed_roles is None:
                route_path = request.endpoint or ''
                if 'admin' in route_path:
                    required_roles = [WorkspaceRole.ADMIN]
                elif 'teacher' in route_path:
                    required_roles = [WorkspaceRole.TEACHER]
                elif 'delegate' in route_path:
                    required_roles = [WorkspaceRole.DELEGATE]
                else:
                    # Default: allow any workspace member
                    required_roles = [WorkspaceRole.MEMBER, WorkspaceRole.DELEGATE, WorkspaceRole.TEACHER,
                                      WorkspaceRole.ADMIN]
            else:
                # Convert string roles to WorkspaceRole enums
                required_roles = []
                for role in (allowed_roles if isinstance(allowed_roles, list) else [allowed_roles]):
                    if isinstance(role, str):
                        try:
                            required_roles.append(WorkspaceRole(role.upper()))
                        except ValueError:
                            abort(500, f"Invalid role: {role}")
                    else:
                        required_roles.append(role)

            # Check if user's role is in allowed roles
            if user_role not in required_roles:
                abort(403,
                      f"Access denied. Required: {[r.value for r in required_roles]}, Your role: {user_role.value}")

            # Store workspace_id in global context for use in the view
            g.current_workspace_id = workspace_id

            return f(*args, **kwargs)

        return decorated_function

    return decorator


# Specific role decorators for convenience
def admin_required(f):
    """Decorator for admin-only routes"""
    return workspace_role_required([WorkspaceRole.ADMIN])(f)


def teacher_required(f):
    """Decorator for teacher-only routes"""
    return workspace_role_required([WorkspaceRole.TEACHER])(f)


def delegate_required(f):
    """Decorator for delegate-only routes"""
    return workspace_role_required([WorkspaceRole.DELEGATE])(f)


def member_required(f):
    """Decorator for any workspace member"""
    return workspace_role_required(
        [WorkspaceRole.MEMBER, WorkspaceRole.DELEGATE, WorkspaceRole.TEACHER, WorkspaceRole.ADMIN])(f)