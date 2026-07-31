"""Make task summary nullable.

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
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column("summary", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.execute(sa.text("UPDATE tasks SET summary = '' WHERE summary IS NULL"))
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column("summary", existing_type=sa.Text(), nullable=False)
