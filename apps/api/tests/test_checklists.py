import importlib.util
import os
from collections.abc import AsyncIterator
from datetime import date, datetime, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
import pytest_asyncio
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_session
from app.main import app
from app.models import BacklogPlan, BacklogPlanItem, Base, Checklist, Task, TaskBacklogLink


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def client(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[TestClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def add_checklist(session_factory: async_sessionmaker[AsyncSession], name: str = "月次決算") -> Checklist:
    async with session_factory() as session:
        checklist = Checklist(name=name, description="概要")
        session.add(checklist)
        await session.commit()
        await session.refresh(checklist)
        return checklist


async def add_task(session_factory: async_sessionmaker[AsyncSession], checklist_id: int, title: str) -> Task:
    async with session_factory() as session:
        task = Task(checklist_id=checklist_id, title=title, summary="本文", estimated_hours=1)
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task


def test_backlog_persistence_migration_upgrade_and_downgrade() -> None:
    path = Path(__file__).parents[1] / "migrations/versions/0008_add_backlog_plan_persistence.py"
    spec = importlib.util.spec_from_file_location("migration_0008", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE checklists (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE tasks (id INTEGER PRIMARY KEY, checklist_id INTEGER NOT NULL)")
        connection.exec_driver_sql("CREATE TABLE checklist_backlog_links (id INTEGER PRIMARY KEY, checklist_id INTEGER NOT NULL, backlog_issue_id INTEGER NOT NULL, backlog_issue_key VARCHAR(255) NOT NULL, backlog_issue_url TEXT NOT NULL, registered_at DATETIME NOT NULL)")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        inspector = inspect(connection)
        assert "checklist_backlog_links" not in inspector.get_table_names()
        assert {"backlog_plans", "backlog_plan_items", "task_backlog_links"} <= set(inspector.get_table_names())
        assert inspector.get_foreign_keys("task_backlog_links")[0]["options"]["ondelete"] == "CASCADE"
        assert any(item["column_names"] == ["task_id"] for item in inspector.get_unique_constraints("task_backlog_links"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert "checklist_backlog_links" in inspect(connection).get_table_names()
    engine.dispose()


@pytest.mark.asyncio
async def test_models_enforce_unique_task_link_and_cascade_with_checklist(session_factory: async_sessionmaker[AsyncSession]) -> None:
    checklist = await add_checklist(session_factory)
    task = await add_task(session_factory, checklist.id, "確認")
    async with session_factory() as session:
        plan = BacklogPlan(checklist_id=checklist.id, start_date=date(2026, 8, 3), end_date=date(2026, 8, 4), expected_assignee_count=1)
        session.add(plan)
        await session.flush()
        session.add(BacklogPlanItem(backlog_plan_id=plan.id, task_id=task.id, title=task.title, summary=task.summary, estimated_hours=task.estimated_hours, assignee_slot=1, start_date=date(2026, 8, 3), due_date=date(2026, 8, 3), depends_on_task_ids=[]))
        session.add(TaskBacklogLink(task_id=task.id, backlog_issue_id=1, backlog_issue_key="PROJ-1", backlog_issue_url="https://example.test/1"))
        await session.commit()
        session.add(TaskBacklogLink(task_id=task.id, backlog_issue_id=2, backlog_issue_key="PROJ-2", backlog_issue_url="https://example.test/2"))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
        checklist_to_delete = await session.get(Checklist, checklist.id)
        assert checklist_to_delete is not None
        await session.delete(checklist_to_delete)
        await session.commit()
        assert await session.scalar(select(BacklogPlan).where(BacklogPlan.id == plan.id)) is None
        assert await session.scalar(select(BacklogPlanItem).where(BacklogPlanItem.task_id == task.id)) is None
        assert await session.scalar(select(TaskBacklogLink).where(TaskBacklogLink.task_id == task.id)) is None


@pytest.mark.asyncio
async def test_checklist_registration_aggregates_tasks(client: TestClient, session_factory: async_sessionmaker[AsyncSession]) -> None:
    checklist = await add_checklist(session_factory)
    first = await add_task(session_factory, checklist.id, "登録済み")
    await add_task(session_factory, checklist.id, "未登録")
    issued_at = datetime(2026, 7, 31, 1, 0, tzinfo=timezone.utc)
    async with session_factory() as session:
        session.add(TaskBacklogLink(task_id=first.id, backlog_issue_id=1, backlog_issue_key="PROJ-1", backlog_issue_url="https://example.test/1", issued_at=issued_at))
        await session.commit()

    item = client.get("/checklists").json()["checklists"][0]
    assert item["task_count"] == 2
    assert item["backlog_registration"] == {"status": "partial", "issued_task_count": 1, "total_task_count": 2, "last_issued_at": "2026-07-31T01:00:00"}
    detail = client.get(f"/checklists/{checklist.id}").json()
    assert detail["backlog_registration"] == item["backlog_registration"]

    async with session_factory() as session:
        second = await session.scalar(select(Task).where(Task.checklist_id == checklist.id, Task.id != first.id))
        assert second is not None
        session.add(TaskBacklogLink(task_id=second.id, backlog_issue_id=2, backlog_issue_key="PROJ-2", backlog_issue_url="https://example.test/2"))
        await session.commit()
    assert client.get(f"/checklists/{checklist.id}").json()["backlog_registration"]["status"] == "registered"


def test_checklist_registration_is_unregistered_for_empty_checklist(client: TestClient) -> None:
    created = client.post("/checklists", json={"name": "空"}).json()
    detail = client.get(f"/checklists/{created['id']}").json()
    assert detail["backlog_registration"] == {"status": "unregistered", "issued_task_count": 0, "total_task_count": 0, "last_issued_at": None}
