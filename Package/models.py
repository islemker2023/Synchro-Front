# Add these to your models.py
import secrets
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Table, Enum, UniqueConstraint, Integer, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone, timedelta
import enum


Base = declarative_base()

# Association table - FIXED: Added Base.metadata and UUID type
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


class Role(Base):
    __tablename__ = 'role'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(80), unique=True)
    description = Column(String(255))


class Workspace(Base):
    __tablename__ = 'workspaces'

    workspace_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=False)
    is_active = Column(Boolean, default=True)

    # Existing relationships
    creator = relationship("Users", back_populates="created_workspaces")
    members = relationship("WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan")

    # NEW relationships to add:
    notices = relationship("Notices", back_populates="workspace", cascade="all, delete-orphan")
    courses = relationship("Courses", back_populates="workspace", cascade="all, delete-orphan")
    assignments = relationship("Assignments", back_populates="workspace", cascade="all, delete-orphan")
    objectives = relationship("Objective", cascade="all, delete-orphan")


    def get_active_courses(self):
        """Get all active courses in this workspace"""
        return [course for course in self.courses if course.is_active]

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
            'total_courses': len([c for c in self.courses if c.is_active]),
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

    # FIXED: Unique constraint - removed db. prefix
    __table_args__ = (
        UniqueConstraint('workspace_id', 'user_id', name='unique_workspace_user'),
    )


class Users(Base):
    __tablename__ = 'users'

    # Your existing fields - FIXED: Use UUID type
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)  # Fixed: renamed from fullname
    profile_picture = Column(String(255), nullable=True)


    # Remember me token fields
    remember_token = Column(String(255))
    remember_token_expiry = Column(DateTime)
    roles = relationship('Role', secondary=roles_users, backref='users')

    # Workspace relationships
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

    def get_user_courses(self, workspace_id):
        """Get courses for a user in a specific workspace"""
        if self.is_workspace_admin(workspace_id) or self.get_workspace_role(workspace_id) == WorkspaceRole.TEACHER:
            # Note: This method would need the db_session passed to it or accessed differently
            # to avoid circular imports. Consider refactoring this logic to a service layer.
            pass
        else:
            # Regular members see courses they're enrolled in
            return []

    def can_create_course(self, workspace_id):
        """Check if user can create courses in workspace"""
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


# Update your existing role-specific tables to include workspace_id
class Admins(Base):
    __tablename__ = 'admins'

    admin_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.workspace_id'), nullable=False)
    # Add any admin-specific fields here

    # Relationships
    user = relationship("Users")
    workspace = relationship("Workspace")


class Teachers(Base):
    __tablename__ = 'teachers'

    teacher_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.workspace_id'), nullable=False)
    # Add any teacher-specific fields here
    department = Column(String(100))  # Optional: teacher's department
    specialization = Column(String(200))  # Optional: teacher's specialization

    # Existing relationships
    user = relationship("Users")
    workspace = relationship("Workspace")

    # NEW relationships to add:
    courses = relationship("Courses", back_populates="teacher")
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
    # Add any delegate-specific fields here

    # Relationships
    user = relationship("Users")
    workspace = relationship("Workspace")


class Notices(Base):
    __tablename__ = 'notices'

    notice_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.workspace_id'), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    posted_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    workspace = relationship("Workspace", back_populates="notices")


class Courses(Base):
    __tablename__ = 'courses'

    course_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.workspace_id'), nullable=False)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey('teachers.teacher_id'), nullable=True)
    course_name = Column(String(100), nullable=False)
    description = Column(Text)
    semester = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    workspace = relationship("Workspace", back_populates="courses")
    teacher = relationship("Teachers", back_populates="courses")
    assignments = relationship("Assignments", back_populates="course", cascade="all, delete-orphan")
    uploaded_files = relationship("UploadedFiles", back_populates="course", cascade="all, delete-orphan")


class Assignments(Base):
    __tablename__ = 'assignments'

    assignment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey('courses.course_id'), nullable=False)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey('teachers.teacher_id'), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.workspace_id'), nullable=False)
    title = Column(String(255), nullable=False)  # Added title field
    description = Column(Text)  # Added description field
    google_form_link = Column(Text, nullable=False)
    due_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    course = relationship("Courses", back_populates="assignments")
    teacher = relationship("Teachers", back_populates="assignments")
    workspace = relationship("Workspace", back_populates="assignments")


class UploadedFiles(Base):
    __tablename__ = 'uploaded_files'

    file_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey('courses.course_id'), nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=False)  # Track who uploaded
    file_name = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)  # Store original name
    file_url = Column(Text, nullable=False)
    file_size = Column(Integer)  # Store file size in bytes
    file_type = Column(String(50))  # Store MIME type
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    course = relationship("Courses", back_populates="uploaded_files")
    uploader = relationship("Users")


class WorkspaceInvitation(Base):
    __tablename__ = 'workspace_invitations'

    invitation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.workspace_id'), nullable=False)
    invited_by = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=False)
    email = Column(String(255), nullable=False)
    invitation_code = Column(String(10), nullable=False, unique=True)
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

    # Unique constraint to prevent duplicate invitations for same email/workspace
    __table_args__ = (
        UniqueConstraint('workspace_id', 'email', 'is_used', name='unique_active_invitation'),
    )

    @classmethod
    def generate_invitation_code(cls):
        """Generate a unique 6-digit invitation code"""
        return secrets.token_hex(3).upper()  # Generates 6-character hex code

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
            email=email.lower(),  # Store email in lowercase for consistency
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
    is_used = Column(Boolean, default=False)  # Track if token has been used

    # Relationships
    user = relationship("Users", backref="password_reset_tokens")

class Objective(Base):
            __tablename__ = 'objectives'

            objective_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
            workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.workspace_id'), nullable=False)
            teacher_id = Column(UUID(as_uuid=True), ForeignKey('teachers.teacher_id'), nullable=False)
            created_by = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=False)  # Admin who created
            title = Column(String(255), nullable=False)
            description = Column(Text)
            due_date = Column(Date, nullable=True)
            priority = Column(Enum(enum.Enum('Priority', 'LOW MEDIUM HIGH')), default='MEDIUM')
            created_at = Column(DateTime, default=datetime.utcnow)
            updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
            is_active = Column(Boolean, default=True)

            # Relationships
            workspace = relationship("Workspace")
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
    order_index = Column(Integer, default=0)  # For ordering sub-objectives
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    completed_by = Column(UUID(as_uuid=True), ForeignKey('users.user_id'), nullable=True)  # Who marked it complete
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    objective = relationship("Objective", back_populates="sub_objectives")
    completer = relationship("Users", foreign_keys=[completed_by])

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


class Priority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"