from datetime import date, datetime

from sqlalchemy import JSON, CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Checklist(Base):
    __tablename__ = "checklists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    backlog_project_key_or_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    tasks: Mapped[list["Task"]] = relationship(back_populates="checklist", order_by="Task.id", cascade="all, delete-orphan")
    backlog_plans: Mapped[list["BacklogPlan"]] = relationship(back_populates="checklist", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (CheckConstraint("priority IN ('low', 'medium', 'high')", name="ck_tasks_priority"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    checklist_id: Mapped[int] = mapped_column(ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_hours: Mapped[float] = mapped_column(Float, nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'medium'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    checklist: Mapped[Checklist] = relationship(back_populates="tasks")
    backlog_plan_items: Mapped[list["BacklogPlanItem"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    backlog_link: Mapped["TaskBacklogLink | None"] = relationship(back_populates="task", cascade="all, delete-orphan", single_parent=True)


class BacklogPlan(Base):
    __tablename__ = "backlog_plans"
    __table_args__ = (
        CheckConstraint("status IN ('planned', 'partial', 'issued')", name="ck_backlog_plans_status"),
        CheckConstraint("expected_assignee_count >= 1", name="ck_backlog_plans_expected_assignee_count"),
        CheckConstraint("start_date <= end_date", name="ck_backlog_plans_date_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    checklist_id: Mapped[int] = mapped_column(ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False, index=True)
    backlog_project_key_or_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_assignee_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'planned'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    checklist: Mapped[Checklist] = relationship(back_populates="backlog_plans")
    items: Mapped[list["BacklogPlanItem"]] = relationship(back_populates="plan", cascade="all, delete-orphan", order_by="BacklogPlanItem.id")


class BacklogPlanItem(Base):
    __tablename__ = "backlog_plan_items"
    __table_args__ = (
        UniqueConstraint("backlog_plan_id", "task_id", name="uq_backlog_plan_items_plan_task"),
        CheckConstraint("assignee_slot >= 1", name="ck_backlog_plan_items_assignee_slot"),
        CheckConstraint("start_date <= due_date", name="ck_backlog_plan_items_date_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    backlog_plan_id: Mapped[int] = mapped_column(ForeignKey("backlog_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_hours: Mapped[float] = mapped_column(Float, nullable=False)
    assignee_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    depends_on_task_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    plan: Mapped[BacklogPlan] = relationship(back_populates="items")
    task: Mapped[Task] = relationship(back_populates="backlog_plan_items")


class TaskBacklogLink(Base):
    __tablename__ = "task_backlog_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, unique=True)
    backlog_issue_id: Mapped[int] = mapped_column(Integer, nullable=False)
    backlog_issue_key: Mapped[str] = mapped_column(String(255), nullable=False)
    backlog_issue_url: Mapped[str] = mapped_column(Text, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    task: Mapped[Task] = relationship(back_populates="backlog_link")
