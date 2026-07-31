"""Add checklist configuration.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "checklists",
        sa.Column("assignee_count", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.add_column("checklists", sa.Column("backlog_project_key_or_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("checklists", "backlog_project_key_or_url")
    op.drop_column("checklists", "assignee_count")
