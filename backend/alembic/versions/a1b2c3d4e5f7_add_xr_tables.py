"""add xr tables

Revision ID: a1b2c3d4e5f7
Revises: c1a2b3d4e5f6
Create Date: 2026-04-28 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, Sequence[str], None] = 'c1a2b3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create xr_sessions and xr_events tables."""
    op.create_table('xr_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('booking_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False, server_default='null'),
        sa.Column('external_session_id', sa.String(length=200), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('request_payload', sa.Text(), nullable=True),
        sa.Column('response_payload', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_retry_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'completed', 'failed', 'cancelled')",
            name='chk_xr_session_status',
        ),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_xr_sessions_booking_id', 'xr_sessions', ['booking_id'], unique=True)
    op.create_index('ix_xr_sessions_status', 'xr_sessions', ['status'], unique=False)
    op.create_index('ix_xr_sessions_provider', 'xr_sessions', ['provider'], unique=False)

    op.create_table('xr_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_id', sa.String(length=200), nullable=False),
        sa.Column('booking_id', sa.Integer(), nullable=True),
        sa.Column('xr_session_id', sa.Integer(), nullable=True),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('payload', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=200), nullable=True),
        sa.Column('signature_verified', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['xr_session_id'], ['xr_sessions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_xr_events_event_id', 'xr_events', ['event_id'], unique=True)
    op.create_index('ix_xr_events_idempotency_key', 'xr_events', ['idempotency_key'], unique=True)
    op.create_index('ix_xr_events_booking_id', 'xr_events', ['booking_id'], unique=False)
    op.create_index('ix_xr_events_provider_type', 'xr_events', ['provider', 'event_type'], unique=False)
    op.create_index('ix_xr_events_processed', 'xr_events', ['processed'], unique=False)


def downgrade() -> None:
    """Drop xr_events then xr_sessions tables."""
    op.drop_index('ix_xr_events_processed', table_name='xr_events')
    op.drop_index('ix_xr_events_provider_type', table_name='xr_events')
    op.drop_index('ix_xr_events_booking_id', table_name='xr_events')
    op.drop_index('ix_xr_events_idempotency_key', table_name='xr_events')
    op.drop_index('ix_xr_events_event_id', table_name='xr_events')
    op.drop_table('xr_events')

    op.drop_index('ix_xr_sessions_provider', table_name='xr_sessions')
    op.drop_index('ix_xr_sessions_status', table_name='xr_sessions')
    op.drop_index('ix_xr_sessions_booking_id', table_name='xr_sessions')
    op.drop_table('xr_sessions')
