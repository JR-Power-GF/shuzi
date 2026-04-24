"""add courses table

Revision ID: 6d49be884006
Revises: 513402d511d6
Create Date: 2026-04-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d49be884006'
down_revision: Union[str, Sequence[str], None] = '513402d511d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('courses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('semester', sa.String(length=20), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['teacher_id'], ['users.id'], ondelete='RESTRICT'),
        sa.CheckConstraint("status IN ('active', 'archived')", name='chk_course_status'),
        sa.UniqueConstraint('name', 'semester', 'teacher_id', name='uq_course_name_semester_teacher'),
    )
    op.create_index('ix_courses_teacher_id', 'courses', ['teacher_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_courses_teacher_id', table_name='courses')
    op.drop_table('courses')
