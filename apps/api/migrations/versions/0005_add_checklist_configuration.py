"""Add checklist configuration.

Revision ID: 0006_checklist_configuration
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_checklist_configuration"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    checklist_columns = {column["name"] for column in sa.inspect(bind).get_columns("checklists")}
    if "assignee_count" not in checklist_columns:
        op.add_column(
            "checklists",
            sa.Column("assignee_count", sa.Integer(), server_default=sa.text("1"), nullable=False),
        )
    if "backlog_project_key_or_url" not in checklist_columns:
        op.add_column("checklists", sa.Column("backlog_project_key_or_url", sa.Text(), nullable=True))

    inspector = sa.inspect(bind)
    if inspector.has_table("tasks"):
        task_columns = {column["name"]: column for column in inspector.get_columns("tasks")}
    else:
        task_columns = {}
    if "summary" in task_columns and not task_columns["summary"]["nullable"]:
        with op.batch_alter_table("tasks") as batch_op:
            batch_op.alter_column("summary", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("checklists")}
    if "backlog_project_key_or_url" in columns:
        op.drop_column("checklists", "backlog_project_key_or_url")
    if "assignee_count" in columns:
        op.drop_column("checklists", "assignee_count")
