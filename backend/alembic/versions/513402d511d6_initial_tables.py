"""initial tables

Revision ID: 513402d511d6
Revises:
Create Date: 2026-04-21 16:50:19.749957

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '513402d511d6'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Create classes table WITHOUT FK to users (to break circular dependency)
    op.create_table('classes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('semester', sa.String(length=20), nullable=False),
    sa.Column('teacher_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )

    # Step 2: Create users table with FK to classes
    op.create_table('users',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('username', sa.String(length=50), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('real_name', sa.String(length=100), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('locked_until', sa.DateTime(), nullable=True),
    sa.Column('failed_login_attempts', sa.Integer(), nullable=False),
    sa.Column('must_change_password', sa.Boolean(), nullable=False),
    sa.Column('primary_class_id', sa.Integer(), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint("role IN ('admin', 'teacher', 'student')", name='chk_user_role'),
    sa.ForeignKeyConstraint(['primary_class_id'], ['classes.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # Step 3: Add FK from classes.teacher_id to users.id (now that users exists)
    op.create_foreign_key('fk_classes_teacher_id', 'classes', 'users', ['teacher_id'], ['id'], ondelete='RESTRICT')

    # Step 4: Create remaining tables
    op.create_table('refresh_tokens',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=500), nullable=False),
    sa.Column('revoked', sa.Boolean(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)

    op.create_table('tasks',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('requirements', sa.Text(), nullable=True),
    sa.Column('class_id', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('deadline', sa.DateTime(), nullable=False),
    sa.Column('allowed_file_types', sa.Text(), nullable=False),
    sa.Column('max_file_size_mb', sa.Integer(), nullable=False),
    sa.Column('allow_late_submission', sa.Boolean(), nullable=False),
    sa.Column('late_penalty_percent', sa.Float(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('grades_published', sa.Boolean(), nullable=False),
    sa.Column('grades_published_at', sa.DateTime(), nullable=True),
    sa.Column('grades_published_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint("status IN ('active', 'archived')", name='chk_task_status'),
    sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['grades_published_by'], ['users.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tasks_class_id'), 'tasks', ['class_id'], unique=False)
    op.create_index(op.f('ix_tasks_created_by'), 'tasks', ['created_by'], unique=False)

    op.create_table('submissions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('task_id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('is_late', sa.Boolean(), nullable=False),
    sa.Column('submitted_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('task_id', 'student_id', name='uq_submission_task_student')
    )
    op.create_index(op.f('ix_submissions_student_id'), 'submissions', ['student_id'], unique=False)
    op.create_index(op.f('ix_submissions_task_id'), 'submissions', ['task_id'], unique=False)

    op.create_table('grades',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('submission_id', sa.Integer(), nullable=False),
    sa.Column('score', sa.Float(), nullable=False),
    sa.Column('penalty_applied', sa.Float(), nullable=True),
    sa.Column('feedback', sa.Text(), nullable=True),
    sa.Column('graded_by', sa.Integer(), nullable=False),
    sa.Column('graded_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['graded_by'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_grades_submission_id'), 'grades', ['submission_id'], unique=True)

    op.create_table('submission_files',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('submission_id', sa.Integer(), nullable=False),
    sa.Column('file_name', sa.String(length=500), nullable=False),
    sa.Column('file_path', sa.String(length=500), nullable=False),
    sa.Column('file_size', sa.BigInteger(), nullable=False),
    sa.Column('file_type', sa.String(length=50), nullable=False),
    sa.Column('uploaded_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_submission_files_submission_id'), 'submission_files', ['submission_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_submission_files_submission_id'), table_name='submission_files')
    op.drop_table('submission_files')
    op.drop_index(op.f('ix_grades_submission_id'), table_name='grades')
    op.drop_table('grades')
    op.drop_index(op.f('ix_submissions_task_id'), table_name='submissions')
    op.drop_index(op.f('ix_submissions_student_id'), table_name='submissions')
    op.drop_table('submissions')
    op.drop_index(op.f('ix_tasks_created_by'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_class_id'), table_name='tasks')
    op.drop_table('tasks')
    op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    # Drop FK from classes before dropping users
    op.drop_constraint('fk_classes_teacher_id', 'classes', type_='foreignkey')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
    op.drop_table('classes')
