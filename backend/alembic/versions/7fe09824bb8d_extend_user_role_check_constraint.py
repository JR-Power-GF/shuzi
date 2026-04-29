"""extend_user_role_check_constraint

Revision ID: 7fe09824bb8d
Revises: 6a5faef33171
Create Date: 2026-04-27 15:07:29.632879

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7fe09824bb8d'
down_revision: Union[str, Sequence[str], None] = '6a5faef33171'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("chk_user_role", "users", type_="check")
    op.create_check_constraint(
        "chk_user_role",
        "users",
        sa.column("role").in_(["admin", "teacher", "student", "facility_manager"]),
    )


def downgrade() -> None:
    op.drop_constraint("chk_user_role", "users", type_="check")
    op.create_check_constraint(
        "chk_user_role",
        "users",
        sa.column("role").in_(["admin", "teacher", "student"]),
    )
