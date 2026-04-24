"""add course_id to tasks

Revision ID: a3f7c9e2015b
Revises: 6d49be884006
Create Date: 2026-04-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f7c9e2015b'
down_revision: Union[str, Sequence[str], None] = '6d49be884006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tasks', sa.Column('course_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_tasks_course_id', 'tasks', 'courses', ['course_id'], ['id'], ondelete='RESTRICT')
    op.create_index('ix_tasks_course_id', 'tasks', ['course_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_tasks_course_id', table_name='tasks')
    op.drop_constraint('fk_tasks_course_id', 'tasks', type_='foreignkey')
    op.drop_column('tasks', 'course_id')
