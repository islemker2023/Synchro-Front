from flask_login import current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileSize
from sqlalchemy.orm import joinedload
from wtforms import EmailField, PasswordField, SubmitField, BooleanField
from wtforms.fields.choices import SelectField
from wtforms.fields.datetime import DateField
from wtforms.fields.form import FormField
from wtforms.fields.list import FieldList
from wtforms.fields.simple import StringField, FileField, TextAreaField
from wtforms.validators import DataRequired, Email, length, Regexp, EqualTo, Length, Optional, ValidationError

from Package import db_session
from Package.models import Teachers, Users


class LoginForm(FlaskForm):
    email = EmailField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), length(min=8)])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')


class ResetPasswordForm(FlaskForm):
    New_Password = PasswordField('New Password', validators=[DataRequired(), length(min=8),  Regexp(
            regex=r'^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]+$',
            message='Password must contain at least one uppercase letter, one number, and one special character.')])
    Confirm_New_Password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('New_Password')])
    Submit = SubmitField('Reset Password')


class SignUpForm(FlaskForm):
    fullname = StringField('FullName', validators=[
        DataRequired(),
        Length(min=2, max=50, message='Your name should at least have 2 characters'),
        Regexp(r'^[A-Za-zÀ-ÿ\-\' ]+$', message='Name can only contain letters, spaces, hyphens, and apostrophes')
    ])
    email = EmailField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8),
        Regexp(
            regex=r'^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]+$',
            message='Password must contain at least one uppercase letter, one number, and one special character.'
        )
    ])
    confirmPassword = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Create Account')


class UpdateProfileForm(FlaskForm):
    full_name = StringField('Full Name',
                            validators=[DataRequired(), Length(min=2, max=100)],
                            render_kw={'class': 'form-control'})

    email = StringField('Email',
                        validators=[DataRequired(), Email()],
                        render_kw={'class': 'form-control'})

    submit = SubmitField('Update Profile', render_kw={'class': 'btn btn-primary'})

    def validate_email(self, email):
        # Check if email is already taken by another user
        user = Users.query.filter(
            Users.email == email.data.lower(),
            Users.user_id != current_user.user_id
        ).first()
        if user:
            raise ValidationError('This email is already registered to another user.')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password',
                                     validators=[DataRequired()],
                                     render_kw={'class': 'form-control'})

    new_password = PasswordField('New Password',
                                 validators=[DataRequired(), Length(min=8)],
                                 render_kw={'class': 'form-control'})

    confirm_password = PasswordField('Confirm New Password',
                                     validators=[DataRequired(),
                                                 EqualTo('new_password', message='Passwords must match')],
                                     render_kw={'class': 'form-control'})

    submit = SubmitField('Change Password', render_kw={'class': 'btn btn-warning'})


class ProfilePictureForm(FlaskForm):
    profile_picture = FileField('Profile Picture',
                                validators=[
                                    FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!'),
                                    FileSize(max_size=5 * 1024 * 1024, message='File size must be less than 5MB')
                                ],
                                render_kw={'class': 'form-control', 'accept': 'image/*'})

    submit = SubmitField('Upload Picture', render_kw={'class': 'btn btn-success'})
class BeforeResetPassword(FlaskForm):
    email = EmailField('Email Address', validators=[DataRequired(), Email()])
    submit = SubmitField('Send Reset Link')


class SubObjectiveForm(FlaskForm):
    """Form for individual sub-objectives"""
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])


class CreateObjectiveForm(FlaskForm):
    """Form for creating new objectives"""
    teacher_id = SelectField('Teacher', validators=[DataRequired()], coerce=str)
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=1000)])
    due_date = DateField('Due Date', validators=[Optional()])
    priority = SelectField('Priority',
                           choices=[('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High')],
                           default='MEDIUM',
                           validators=[DataRequired()])
    sub_objectives = FieldList(FormField(SubObjectiveForm), min_entries=1, max_entries=10)

    def __init__(self, workspace_id, *args, **kwargs):
        super(CreateObjectiveForm, self).__init__(*args, **kwargs)

        # Populate teacher choices
        teachers = db_session.query(Teachers).join(Users).filter(
            Teachers.workspace_id == workspace_id
        ).options(joinedload(Teachers.user)).all()

        self.teacher_id.choices = [('', 'Select a teacher')] + [
            (str(teacher.teacher_id), teacher.user.full_name)
            for teacher in teachers
        ]

    def validate_teacher_id(self, field):
        """Custom validation for teacher_id"""
        if field.data:
            teacher = Teachers.query.filter_by(teacher_id=field.data).first()
            if not teacher:
                raise ValidationError('Invalid teacher selected.')


class EditObjectiveForm(FlaskForm):
    """Form for editing existing objectives"""
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=1000)])
    due_date = DateField('Due Date', validators=[Optional()])
    priority = SelectField('Priority',
                           choices=[('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High')],
                           validators=[DataRequired()])
    sub_objectives = FieldList(FormField(SubObjectiveForm), min_entries=0, max_entries=10)

