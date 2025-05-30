import secrets
import uuid

from prompt_toolkit.shortcuts import message_dialog
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Table, Enum, UniqueConstraint, Integer, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone, timedelta
import enum

Base = declarative_base()

# Association table for roles and users
roles_users = Table('roles_users', Base.metadata,
                    Column('user_id', UUID(as_uuid=True), ForeignKey('users.user_id'), primary_key=True),
                    Column('role_id', UUID(as_uuid=True), ForeignKey('role.id'), primary_key=True)
                    )


# Workspace Role Enum
class WorkspaceRole(enum.Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    DELEGATE = "delegate"
    MEMBER = "member"


# Priority Enum (moved to top for proper usage)
class Priority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Role(Base):
    __tablename__ = 'role'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(80), unique=True)
    description = Column(String(255))


class Users(Base):
    __tablename__ = 'users'

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    profile_picture = Column(String(255), nullable=True)

    # Remember me token fields
    remember_token = Column(String(255))
    remember_token_expiry = Column(DateTime)

    # Relationships
    roles = relationship('Role', secondary=roles_users, backref='users')
    events = relationship("Events", back_populates="creator")
    created_workspaces = relationship("Workspace", back_populates="creator")
    workspace_memberships = relationship("WorkspaceMember", back_populates="user")

    # Workspace helper methods
    def get_workspaces(self):
        """Get all workspaces this user is a member of"""
        return [membership.workspace for membership in self.workspace_memberships if membership.is_active]

    def get_workspace_role(self, workspace_id):
        """Get user's role in a specific workspace"""
        membership = next((m for m in self.workspace_memberships
                           if m.workspace_id == workspace_id and m.is_active), None)
        return membership.role if membership else None

    def is_workspace_admin(self, workspace_id):
        """Check if user is admin in a specific workspace"""
        return self.get_workspace_role(workspace_id) == WorkspaceRole.ADMIN

    def can_manage_workspace(self, workspace_id):
        """Check if user can manage a specific workspace"""
        role = self.get_workspace_role(workspace_id)
        return role in [WorkspaceRole.ADMIN, WorkspaceRole.TEACHER]

    def can_create_folder(self, workspace_id):
        """Check if user can create folders in workspace"""
        role = self.get_workspace_role(workspace_id)
        return role in [WorkspaceRole.ADMIN, WorkspaceRole.TEACHER]

    def can_create_assignment(self, workspace_id):
        """Check if user can create assignments in workspace"""
        role = self.get_workspace_role(workspace_id)
        return role in [WorkspaceRole.ADMIN, WorkspaceRole.TEACHER]

    def can_upload_files(self, workspace_id):
        """Check if user can upload files in workspace"""
        role = self.get_workspace_role(workspace_id)
        return role in [WorkspaceRole.ADMIN, WorkspaceRole.TEACHER]

    def can_post_notices(self, workspace_id):
        """Check if user can post notices in workspace"""
        role = self.get_workspace_role(workspace_id)
        return role in [WorkspaceRole.ADMIN, WorkspaceRole.TEACHER, WorkspaceRole.DELEGATE]


class Workspace(Base):
    __tablename__ = 'workspaces'

    workspace_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=False)
    is_active = Column(Boolean, default=True)

    # Relationships
    creator = relationship("Users", back_populates="created_workspaces")
    members = relationship("WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan")
    notices = relationship("Notices", back_populates="workspace", cascade="all, delete-orphan")
    folders = relationship("Folders", back_populates="workspace", cascade="all, delete-orphan")
    assignments = relationship("Assignments", back_populates="workspace", cascade="all, delete-orphan")
    objectives = relationship("Objective", back_populates="workspace", cascade="all, delete-orphan")
    events = relationship("Events", back_populates="workspace", cascade="all, delete-orphan")

    def get_active_folders(self):
        """Get all active folders in this workspace"""
        return [folder for folder in self.folders if folder.is_active]

    def get_recent_notices(self, limit=5):
        """Get recent notices for this workspace"""
        return sorted([notice for notice in self.notices if notice.is_active],
                      key=lambda x: x.posted_at, reverse=True)[:limit]

    def get_upcoming_assignments(self, limit=10):
        """Get upcoming assignments in this workspace"""
        from datetime import date
        return sorted([assignment for assignment in self.assignments
                       if assignment.is_active and assignment.due_date >= date.today()],
                      key=lambda x: x.due_date)[:limit]

    def get_workspace_stats(self):
        """Get basic statistics for this workspace"""
        return {
            'total_members': len([m for m in self.members if m.is_active]),
            'total_folders': len([f for f in self.folders if f.is_active]),
            'total_assignments': len([a for a in self.assignments if a.is_active]),
            'recent_notices': len(self.get_recent_notices()),
            'upcoming_assignments': len(self.get_upcoming_assignments())
        }

    def get_objectives_overview(self):
        """Get overview of all objectives in workspace"""
        active_objectives = [obj for obj in self.objectives if obj.is_active]

        total_objectives = len(active_objectives)
        completed_objectives = len([obj for obj in active_objectives if obj.get_completion_percentage() == 100])
        overdue_objectives = len(
            [obj for obj in active_objectives if obj.is_overdue() and obj.get_completion_percentage() < 100])

        # Group by teacher
        teacher_stats = {}
        for obj in active_objectives:
            teacher_name = obj.teacher.user.full_name
            if teacher_name not in teacher_stats:
                teacher_stats[teacher_name] = {
                    'total': 0,
                    'completed': 0,
                    'avg_completion': 0
                }

            teacher_stats[teacher_name]['total'] += 1
            if obj.get_completion_percentage() == 100:
                teacher_stats[teacher_name]['completed'] += 1

        # Calculate average completion for each teacher
        for teacher_name in teacher_stats:
            teacher_objectives = [obj for obj in active_objectives if obj.teacher.user.full_name == teacher_name]
            if teacher_objectives:
                avg_completion = sum([obj.get_completion_percentage() for obj in teacher_objectives]) / len(
                    teacher_objectives)
                teacher_stats[teacher_name]['avg_completion'] = round(avg_completion, 1)

        return {
            'total_objectives': total_objectives,
            'completed_objectives': completed_objectives,
            'overdue_objectives': overdue_objectives,
            'teacher_stats': teacher_stats
        }


class WorkspaceMember(Base):
    __tablename__ = 'workspace_members'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.workspace_id'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=False)
    role = Column(Enum(WorkspaceRole), nullable=False, default=WorkspaceRole.MEMBER)
    joined_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    workspace = relationship("Workspace", back_populates="members")
    user = relationship("Users", back_populates="workspace_memberships")

    # Unique constraint
    __table_args__ = (
        UniqueConstraint('workspace_id', 'user_id', name='unique_workspace_user'),
    )


class Admins(Base):
    __tablename__ = 'admins'

    admin_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.workspace_id'), nullable=False)

    # Relationships
    user = relationship("Users")
    workspace = relationship("Workspace")


class Teachers(Base):
    __tablename__ = 'teachers'

    teacher_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.workspace_id'), nullable=False)
    department = Column(String(100))
    specialization = Column(String(200))

    # Relationships
    user = relationship("Users")
    workspace = relationship("Workspace")
    folders = relationship("Folders", back_populates="teacher")
    assignments = relationship("Assignments", back_populates="teacher")
    objectives = relationship("Objective", back_populates="teacher")

    def get_objectives_summary(self):
        """Get summary of teacher's objectives"""
        active_objectives = [obj for obj in self.objectives if obj.is_active]

        total_objectives = len(active_objectives)
        completed_objectives = len([obj for obj in active_objectives if obj.get_completion_percentage() == 100])
        in_progress_objectives = len([obj for obj in active_objectives if 0 < obj.get_completion_percentage() < 100])
        overdue_objectives = len(
            [obj for obj in active_objectives if obj.is_overdue() and obj.get_completion_percentage() < 100])

        overall_completion = 0
        if total_objectives > 0:
            total_completion = sum([obj.get_completion_percentage() for obj in active_objectives])
            overall_completion = round(total_completion / total_objectives, 1)

        return {
            'total_objectives': total_objectives,
            'completed_objectives': completed_objectives,
            'in_progress_objectives': in_progress_objectives,
            'overdue_objectives': overdue_objectives,
            'overall_completion': overall_completion
        }


class Delegates(Base):
    __tablename__ = 'delegates'

    delegate_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.workspace_id'), nullable=False)

    # Relationships
    user = relationship("Users")
    workspace = relationship("Workspace")


class Notices(Base):
    __tablename__ = 'notices'

    notice_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.workspace_id'), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    posted_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    workspace = relationship("Workspace", back_populates="notices")
    author = relationship("Users")  # Added relationship to user who posted notice


class Folders(Base):
    __tablename__ = 'folders'

    folder_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.workspace_id'), nullable=False)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey('teachers.teacher_id'), nullable=True)
    folder_name = Column(String(100), nullable=False)
    description = Column(Text)
    color = Column(String(7), default='#6366f1')
    icon = Column(String(50), default='folder')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    workspace = relationship("Workspace", back_populates="folders")
    teacher = relationship("Teachers", back_populates="folders")
    assignments = relationship("Assignments", back_populates="folder", cascade="all, delete-orphan")
    uploaded_files = relationship("UploadedFiles", back_populates="folder", cascade="all, delete-orphan")

    def get_files_count(self):
        """Get count of active files in this folder"""
        return len([f for f in self.uploaded_files if f.is_active])

    def get_assignments_count(self):
        """Get count of active assignments in this folder"""
        return len([a for a in self.assignments if a.is_active])

    def get_recent_activity(self, limit=5):
        """Get recent activity in this folder"""
        activities = []

        # Add recent file uploads
        for file in self.uploaded_files:
            if file.is_active:
                activities.append({
                    'type': 'file_upload',
                    'timestamp': file.uploaded_at,
                    'description': f"File '{file.original_filename}' uploaded",
                    'user': file.uploader.full_name if file.uploader else 'Unknown'
                })

        # Add recent assignments
        for assignment in self.assignments:
            if assignment.is_active:
                activities.append({
                    'type': 'assignment_created',
                    'timestamp': assignment.created_at,
                    'description': f"Assignment '{assignment.title}' created",
                    'user': assignment.teacher.user.full_name if assignment.teacher else 'Unknown'
                })

        # Sort by timestamp and return most recent
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        return activities[:limit]


class Assignments(Base):
    __tablename__ = 'assignments'

    assignment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    folder_id = Column(UUID(as_uuid=True), ForeignKey('folders.folder_id'), nullable=False)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey('teachers.teacher_id'), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.workspace_id'), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    google_form_link = Column(Text, nullable=False)
    due_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    folder = relationship("Folders", back_populates="assignments")
    teacher = relationship("Teachers", back_populates="assignments")
    workspace = relationship("Workspace", back_populates="assignments")


class UploadedFiles(Base):
    __tablename__ = 'uploaded_files'

    file_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    folder_id = Column(UUID(as_uuid=True), ForeignKey('folders.folder_id'), nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=False)
    file_name = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_url = Column(Text, nullable=False)
    file_size = Column(Integer)
    file_type = Column(String(50))
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    folder = relationship("Folders", back_populates="uploaded_files")
    uploader = relationship("Users")


class WorkspaceInvitation(Base):
    __tablename__ = 'workspace_invitations'

    invitation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.workspace_id'), nullable=False)
    invited_by = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=False)
    email = Column(String(255), nullable=False)
    invitation_code = Column(String(32), nullable=False, unique=True)  # Fixed length
    role = Column(Enum(WorkspaceRole), nullable=False, default=WorkspaceRole.MEMBER)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    used_at = Column(DateTime, nullable=True)
    used_by = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=True)

    # Relationships
    workspace = relationship("Workspace")
    inviter = relationship("Users", foreign_keys=[invited_by])
    user_who_used = relationship("Users", foreign_keys=[used_by])

    # Fixed unique constraint
    __table_args__ = (
        UniqueConstraint('workspace_id', 'email', name='unique_workspace_email'),
    )

    @classmethod
    def generate_invitation_code(cls):
        """Generate a unique invitation code"""
        return secrets.token_hex(16).upper()

    def is_expired(self):
        """Check if invitation has expired"""
        return datetime.utcnow() > self.expires_at

    def is_valid(self):
        """Check if invitation is valid (not used and not expired)"""
        return not self.is_used and not self.is_expired()

    @classmethod
    def create_invitation(cls, workspace_id, email, invited_by_user_id, role=WorkspaceRole.MEMBER, expires_in_days=7):
        """Create a new workspace invitation"""
        invitation = cls(
            workspace_id=workspace_id,
            invited_by=invited_by_user_id,
            email=email.lower(),
            invitation_code=cls.generate_invitation_code(),
            role=role,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days)
        )
        return invitation


class ResetPassword(Base):
    __tablename__ = 'reset_password'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=False)
    token = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False)

    # Relationships
    user = relationship("Users", backref="password_reset_tokens")


class Objective(Base):
    __tablename__ = 'objectives'

    objective_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.workspace_id'), nullable=False)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey('teachers.teacher_id'), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    due_date = Column(Date, nullable=True)
    priority = Column(Enum(Priority), default=Priority.MEDIUM)  # Fixed enum usage
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    workspace = relationship("Workspace", back_populates="objectives")
    teacher = relationship("Teachers", back_populates="objectives")
    creator = relationship("Users")
    sub_objectives = relationship("SubObjective", back_populates="objective", cascade="all, delete-orphan")

    def get_completion_percentage(self):
        """Calculate completion percentage based on completed sub-objectives"""
        if not self.sub_objectives:
            return 0

        active_sub_objectives = [sub for sub in self.sub_objectives if sub.is_active]
        if not active_sub_objectives:
            return 0

        completed_count = len([sub for sub in active_sub_objectives if sub.is_completed])
        return round((completed_count / len(active_sub_objectives)) * 100, 1)

    def is_overdue(self):
        """Check if objective is overdue"""
        if not self.due_date:
            return False
        from datetime import date
        return date.today() > self.due_date

    def get_status(self):
        """Get objective status based on completion and due date"""
        completion = self.get_completion_percentage()
        if completion == 100:
            return "COMPLETED"
        elif self.is_overdue():
            return "OVERDUE"
        elif completion > 0:
            return "IN_PROGRESS"
        else:
            return "NOT_STARTED"


class SubObjective(Base):
    __tablename__ = 'sub_objectives'

    sub_objective_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    objective_id = Column(UUID(as_uuid=True), ForeignKey('objectives.objective_id'), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    order_index = Column(Integer, default=0)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    completed_by = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    objective = relationship("Objective", back_populates="sub_objectives")
    completer = relationship("Users")

    def mark_completed(self, user_id):
        """Mark sub-objective as completed"""
        self.is_completed = True
        self.completed_at = datetime.utcnow()
        self.completed_by = user_id

    def mark_incomplete(self):
        """Mark sub-objective as incomplete"""
        self.is_completed = False
        self.completed_at = None
        self.completed_by = None


class Events(Base):
    __tablename__ = 'events'

    events_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.workspace_id'), nullable=False)
    date = Column(Date, nullable=False)
    description = Column(Text)
    time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    creator = relationship("Users", back_populates="events")
    workspace = relationship("Workspace", back_populates="events")

class Message(Base):  # Use db.Model if using Flask SQLAlchemy
    __tablename__ = 'message'

    message_id = Column(String(128), primary_key=True, unique=True, nullable=False, default=uuid.uuid4)  # Gmail message ID
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.workspace_id'), nullable=False)
    message_content = Column(Text, nullable=False)
    send_to = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    # Relationships
    user = relationship("Users", backref="messages")
    workspace = relationship("Workspace", backref="messages")

    @classmethod
    def create_message(cls, workspace_id, message_id, user_id):
        """Create a new Message instance"""
        return cls(
            workspace_id=workspace_id,
            message_id=message_id,
            user_id=user_id
        )
