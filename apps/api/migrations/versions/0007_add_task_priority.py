"""Add task priority.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("priority", sa.String(length=6), nullable=True))
    op.execute(sa.text("UPDATE tasks SET priority = 'medium' WHERE priority IS NULL"))
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column("priority", existing_type=sa.String(length=6), nullable=False)
        batch_op.alter_column(
            "priority", existing_type=sa.String(length=6), server_default="medium"
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("priority")
