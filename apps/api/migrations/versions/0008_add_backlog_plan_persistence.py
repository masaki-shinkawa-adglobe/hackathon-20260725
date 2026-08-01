"""Add Backlog plan persistence and task issue links.

Revision ID: 0008_add_backlog_plan_persistence
Revises: 0007_add_task_priority
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_add_backlog_plan_persistence"
down_revision: str | Sequence[str] | None = "0007_add_task_priority"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("backlog_plans", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("checklist_id", sa.Integer(), nullable=False), sa.Column("backlog_project_key_or_url", sa.Text(), nullable=True), sa.Column("start_date", sa.Date(), nullable=False), sa.Column("end_date", sa.Date(), nullable=False), sa.Column("expected_assignee_count", sa.Integer(), nullable=False), sa.Column("status", sa.String(length=10), server_default=sa.text("'planned'"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.CheckConstraint("status IN ('planned', 'partial', 'issued')", name="ck_backlog_plans_status"), sa.CheckConstraint("expected_assignee_count >= 1", name="ck_backlog_plans_expected_assignee_count"), sa.CheckConstraint("start_date <= end_date", name="ck_backlog_plans_date_range"), sa.ForeignKeyConstraint(["checklist_id"], ["checklists.id"], ondelete="CASCADE"))
    op.create_index("ix_backlog_plans_checklist_id", "backlog_plans", ["checklist_id"])
    op.create_table("backlog_plan_items", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("backlog_plan_id", sa.Integer(), nullable=False), sa.Column("task_id", sa.Integer(), nullable=False), sa.Column("title", sa.String(length=255), nullable=False), sa.Column("summary", sa.Text(), nullable=True), sa.Column("estimated_hours", sa.Float(), nullable=False), sa.Column("assignee_slot", sa.Integer(), nullable=False), sa.Column("start_date", sa.Date(), nullable=False), sa.Column("due_date", sa.Date(), nullable=False), sa.Column("depends_on_task_ids", sa.JSON(), nullable=False), sa.CheckConstraint("assignee_slot >= 1", name="ck_backlog_plan_items_assignee_slot"), sa.CheckConstraint("start_date <= due_date", name="ck_backlog_plan_items_date_range"), sa.ForeignKeyConstraint(["backlog_plan_id"], ["backlog_plans.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"), sa.UniqueConstraint("backlog_plan_id", "task_id", name="uq_backlog_plan_items_plan_task"))
    op.create_index("ix_backlog_plan_items_backlog_plan_id", "backlog_plan_items", ["backlog_plan_id"])
    op.create_index("ix_backlog_plan_items_task_id", "backlog_plan_items", ["task_id"])
    op.create_table("task_backlog_links", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("task_id", sa.Integer(), nullable=False), sa.Column("backlog_issue_id", sa.Integer(), nullable=False), sa.Column("backlog_issue_key", sa.String(length=255), nullable=False), sa.Column("backlog_issue_url", sa.Text(), nullable=False), sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"), sa.UniqueConstraint("task_id", name="uq_task_backlog_links_task_id"))
    op.drop_table("checklist_backlog_links")


def downgrade() -> None:
    op.drop_table("task_backlog_links")
    op.drop_index("ix_backlog_plan_items_task_id", table_name="backlog_plan_items")
    op.drop_index("ix_backlog_plan_items_backlog_plan_id", table_name="backlog_plan_items")
    op.drop_table("backlog_plan_items")
    op.drop_index("ix_backlog_plans_checklist_id", table_name="backlog_plans")
    op.drop_table("backlog_plans")
    op.create_table("checklist_backlog_links", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("checklist_id", sa.Integer(), nullable=False), sa.Column("backlog_issue_id", sa.Integer(), nullable=False), sa.Column("backlog_issue_key", sa.String(length=255), nullable=False), sa.Column("backlog_issue_url", sa.Text(), nullable=False), sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.ForeignKeyConstraint(["checklist_id"], ["checklists.id"], ondelete="CASCADE"), sa.UniqueConstraint("checklist_id", name="uq_checklist_backlog_links_checklist_id"))
