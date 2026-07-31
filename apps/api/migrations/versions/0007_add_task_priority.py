"""Add task priority.

Revision ID: 0007_add_task_priority
Revises: 0006_checklist_configuration
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_add_task_priority"
down_revision: str | Sequence[str] | None = "0006_checklist_configuration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(
            sa.Column("priority", sa.String(length=10), server_default=sa.text("'medium'"), nullable=False)
        )
        batch_op.create_check_constraint(
            "ck_tasks_priority", "priority IN ('low', 'medium', 'high')"
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint("ck_tasks_priority", type_="check")
        batch_op.drop_column("priority")
