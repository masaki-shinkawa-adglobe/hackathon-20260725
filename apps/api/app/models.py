from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Checklist(Base):
    __tablename__ = "checklists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    tasks: Mapped[list["Task"]] = relationship(back_populates="checklist", order_by="Task.id")
    backlog_link: Mapped["ChecklistBacklogLink | None"] = relationship(
        back_populates="checklist", cascade="all, delete-orphan", single_parent=True
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    checklist_id: Mapped[int] = mapped_column(
        ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_hours: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    checklist: Mapped[Checklist] = relationship(back_populates="tasks")


class ChecklistBacklogLink(Base):
    __tablename__ = "checklist_backlog_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    checklist_id: Mapped[int] = mapped_column(
        ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    backlog_issue_id: Mapped[int] = mapped_column(Integer, nullable=False)
    backlog_issue_key: Mapped[str] = mapped_column(String(255), nullable=False)
    backlog_issue_url: Mapped[str] = mapped_column(Text, nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    checklist: Mapped[Checklist] = relationship(back_populates="backlog_link")
