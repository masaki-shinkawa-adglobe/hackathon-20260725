"""Add checklist Backlog links.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "checklist_backlog_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("checklist_id", sa.Integer(), nullable=False),
        sa.Column("backlog_issue_id", sa.Integer(), nullable=False),
        sa.Column("backlog_issue_key", sa.String(length=255), nullable=False),
        sa.Column("backlog_issue_url", sa.Text(), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["checklist_id"], ["checklists.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("checklist_id", name="uq_checklist_backlog_links_checklist_id"),
    )


def downgrade() -> None:
    op.drop_table("checklist_backlog_links")
