import importlib.util
import os
from collections.abc import AsyncIterator
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
import pytest_asyncio
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_session
from app.main import app
from app.models import Base, Checklist, Task


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


async def add_checklist_and_task(
    session_factory: async_sessionmaker[AsyncSession], *, priority: str = "high"
) -> tuple[Checklist, Task]:
    async with session_factory() as session:
        checklist = Checklist(name="月次決算")
        session.add(checklist)
        await session.flush()
        task = Task(
            checklist_id=checklist.id,
            title="仕訳確認",
            summary="仕訳を確認する",
            estimated_hours=2,
            priority=priority,
        )
        session.add(task)
        await session.commit()
        await session.refresh(checklist)
        await session.refresh(task)
        return checklist, task


@pytest.mark.asyncio
async def test_get_task_returns_checklist_name_and_task(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist, task = await add_checklist_and_task(session_factory)

    response = client.get(f"/checklists/{checklist.id}/tasks/{task.id}")

    assert response.status_code == 200
    assert response.json() == {
        "checklist_name": "月次決算",
        "task": {
            "id": task.id,
            "checklist_id": checklist.id,
            "title": "仕訳確認",
            "summary": "仕訳を確認する",
            "estimated_hours": 2.0,
            "priority": "high",
        },
    }


@pytest.mark.asyncio
async def test_update_task_normalizes_values_and_persists(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist, task = await add_checklist_and_task(session_factory)

    response = client.patch(
        f"/checklists/{checklist.id}/tasks/{task.id}",
        json={"title": "  仕訳を確定  ", "summary": "  ", "estimated_hours": 2.5, "priority": "low"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": task.id,
        "checklist_id": checklist.id,
        "title": "仕訳を確定",
        "summary": None,
        "estimated_hours": 2.5,
        "priority": "low",
    }
    async with session_factory() as session:
        updated = await session.scalar(select(Task).where(Task.id == task.id))
        assert updated is not None
        assert (updated.title, updated.summary, updated.estimated_hours, updated.priority) == (
            "仕訳を確定", None, 2.5, "low"
        )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": "valid", "summary": None, "estimated_hours": 1},
        {"title": "valid", "summary": None, "estimated_hours": 1, "priority": "urgent"},
        {"title": "   ", "summary": None, "estimated_hours": 1, "priority": "medium"},
        {"title": "valid", "summary": None, "estimated_hours": 0, "priority": "medium"},
        {"title": "valid", "summary": None, "estimated_hours": "Infinity", "priority": "medium"},
    ],
)
@pytest.mark.asyncio
async def test_update_task_rejects_invalid_input_without_changing_task(
    client: TestClient,
    session_factory: async_sessionmaker[AsyncSession],
    payload: dict[str, object],
) -> None:
    checklist, task = await add_checklist_and_task(session_factory)

    response = client.patch(f"/checklists/{checklist.id}/tasks/{task.id}", json=payload)

    assert response.status_code == 422
    async with session_factory() as session:
        unchanged = await session.scalar(select(Task).where(Task.id == task.id))
        assert unchanged is not None
        assert (unchanged.title, unchanged.summary, unchanged.estimated_hours, unchanged.priority) == (
            "仕訳確認", "仕訳を確認する", 2, "high"
        )


@pytest.mark.asyncio
async def test_task_routes_return_not_found_for_missing_or_mismatched_parent(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist, task = await add_checklist_and_task(session_factory)
    async with session_factory() as session:
        other = Checklist(name="別チェックリスト")
        session.add(other)
        await session.commit()
        await session.refresh(other)

    for method, path, payload in [
        (client.get, f"/checklists/999/tasks/{task.id}", None),
        (client.get, f"/checklists/{other.id}/tasks/{task.id}", None),
        (client.patch, f"/checklists/{other.id}/tasks/{task.id}", {"title": "変更", "summary": None, "estimated_hours": 1, "priority": "medium"}),
    ]:
        response = method(path, json=payload) if payload is not None else method(path)
        assert response.status_code == 404
        assert response.json() == {"detail": "Checklist or task not found"}


def test_task_detail_openapi_schemas() -> None:
    schemas = app.openapi()["components"]["schemas"]
    assert schemas["TaskUpdateRequest"]["required"] == ["title", "summary", "estimated_hours", "priority"]
    assert schemas["TaskUpdateRequest"]["properties"]["priority"]["enum"] == ["high", "medium", "low"]
    assert schemas["TaskResponse"]["properties"]["priority"]["enum"] == ["high", "medium", "low"]
    assert app.openapi()["paths"]["/checklists/{checklist_id}/tasks/{task_id}"]["get"]["responses"]["200"]


def test_task_priority_migration_upgrade_and_downgrade() -> None:
    migration_path = Path(__file__).parents[1] / "migrations/versions/0007_add_task_priority.py"
    spec = importlib.util.spec_from_file_location("migration_0007", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title VARCHAR(255) NOT NULL)")
        connection.exec_driver_sql("INSERT INTO tasks (id, title) VALUES (1, '既存タスク')")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        columns = {column["name"]: column for column in inspect(connection).get_columns("tasks")}
        assert not columns["priority"]["nullable"]
        assert connection.exec_driver_sql("SELECT priority FROM tasks WHERE id = 1").scalar_one() == "medium"
        connection.exec_driver_sql("INSERT INTO tasks (id, title) VALUES (2, '新規タスク')")
        assert connection.exec_driver_sql("SELECT priority FROM tasks WHERE id = 2").scalar_one() == "medium"
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert "priority" not in {column["name"] for column in inspect(connection).get_columns("tasks")}
    engine.dispose()
