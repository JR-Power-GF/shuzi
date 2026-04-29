"""add venue availability and blackout tables

Revision ID: c1a2b3d4e5f6
Revises: eaa79625a9ad
Create Date: 2026-04-27 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a2b3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'eaa79625a9ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('venue_availability',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('venue_id', sa.Integer(), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.CheckConstraint('day_of_week BETWEEN 0 AND 6', name='chk_availability_dow'),
        sa.ForeignKeyConstraint(['venue_id'], ['venues.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('venue_id', 'day_of_week', 'start_time', 'end_time', name='uq_availability_slot'),
    )
    op.create_index(op.f('ix_venue_availability_venue_id'), 'venue_availability', ['venue_id'], unique=False)

    op.create_table('venue_blackout',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('venue_id', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.String(length=200), nullable=True),
        sa.CheckConstraint('end_date >= start_date', name='chk_blackout_date_range'),
        sa.ForeignKeyConstraint(['venue_id'], ['venues.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_venue_blackout_venue_id'), 'venue_blackout', ['venue_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_venue_blackout_venue_id'), table_name='venue_blackout')
    op.drop_table('venue_blackout')
    op.drop_index(op.f('ix_venue_availability_venue_id'), table_name='venue_availability')
    op.drop_table('venue_availability')
