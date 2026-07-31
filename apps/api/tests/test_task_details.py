import os
from collections.abc import AsyncIterator
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Column, Float, Integer, MetaData, String, Table, Text, create_engine, inspect, select
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


async def add_task(session_factory: async_sessionmaker[AsyncSession]) -> tuple[Checklist, Task]:
    async with session_factory() as session:
        checklist = Checklist(name="出張準備")
        session.add(checklist)
        await session.flush()
        task = Task(
            checklist_id=checklist.id,
            title="航空券を手配",
            summary="往復便を予約する。",
            estimated_hours=1.0,
            priority="high",
        )
        session.add(task)
        await session.commit()
        await session.refresh(checklist)
        await session.refresh(task)
        return checklist, task


@pytest.mark.asyncio
async def test_get_task_returns_checklist_name_and_priority(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist, task = await add_task(session_factory)

    response = client.get(f"/checklists/{checklist.id}/tasks/{task.id}")

    assert response.status_code == 200
    assert response.json() == {
        "checklist_name": "出張準備",
        "task": {
            "id": task.id,
            "checklist_id": checklist.id,
            "title": "航空券を手配",
            "summary": "往復便を予約する。",
            "estimated_hours": 1.0,
            "priority": "high",
        },
    }


@pytest.mark.asyncio
async def test_task_detail_returns_not_found_for_missing_or_mismatched_parent(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist, task = await add_task(session_factory)

    assert client.get(f"/checklists/{checklist.id}/tasks/999").status_code == 404
    assert client.get(f"/checklists/999/tasks/{task.id}").status_code == 404


@pytest.mark.asyncio
async def test_patch_task_updates_all_editable_fields(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist, task = await add_task(session_factory)

    response = client.patch(
        f"/checklists/{checklist.id}/tasks/{task.id}",
        json={"title": "  宿泊先を予約  ", "summary": None, "estimated_hours": 2.5, "priority": "low"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": task.id,
        "checklist_id": checklist.id,
        "title": "宿泊先を予約",
        "summary": None,
        "estimated_hours": 2.5,
        "priority": "low",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"title": "", "summary": None, "estimated_hours": 1, "priority": "medium"},
        {"title": "有効", "summary": None, "estimated_hours": 0, "priority": "medium"},
        {"title": "有効", "summary": None, "estimated_hours": "Infinity", "priority": "medium"},
        {"title": "有効", "summary": None, "estimated_hours": 1, "priority": "urgent"},
    ],
)
async def test_patch_task_rejects_invalid_values(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession], payload: dict[str, object]
) -> None:
    checklist, task = await add_task(session_factory)
    assert client.patch(f"/checklists/{checklist.id}/tasks/{task.id}", json=payload).status_code == 422


@pytest.mark.asyncio
async def test_patch_task_returns_not_found_for_missing_or_mismatched_parent(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist, task = await add_task(session_factory)
    payload = {"title": "更新", "summary": "本文", "estimated_hours": 1, "priority": "medium"}

    assert client.patch(f"/checklists/{checklist.id}/tasks/999", json=payload).status_code == 404
    assert client.patch(f"/checklists/999/tasks/{task.id}", json=payload).status_code == 404


def test_task_detail_openapi_schemas() -> None:
    openapi = app.openapi()
    assert "get" in openapi["paths"]["/checklists/{checklist_id}/tasks/{task_id}"]
    assert "patch" in openapi["paths"]["/checklists/{checklist_id}/tasks/{task_id}"]
    schema = openapi["components"]["schemas"]["TaskUpdateRequest"]
    assert schema["required"] == ["title", "estimated_hours", "priority"]
    assert schema["properties"]["priority"]["enum"] == ["low", "medium", "high"]


def test_priority_migration_adds_default_and_allowed_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_path = tmp_path / "priority.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    command.stamp(config, "0006_checklist_configuration")

    metadata = MetaData()
    tasks = Table(
        "tasks",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("checklist_id", Integer, nullable=False),
        Column("title", String(255), nullable=False),
        Column("summary", String, nullable=True),
        Column("estimated_hours", Float, nullable=False),
    )
    engine = create_engine(f"sqlite:///{database_path}")
    metadata.create_all(engine)

    command.upgrade(config, "0007_add_task_priority")
    columns = {column["name"]: column for column in inspect(engine).get_columns("tasks")}
    assert not columns["priority"]["nullable"]
    migrated_tasks = Table("tasks", MetaData(), autoload_with=engine)
    with engine.begin() as connection:
        connection.execute(migrated_tasks.insert(), {"checklist_id": 1, "title": "既定値", "estimated_hours": 1})
        assert connection.execute(select(migrated_tasks.c.priority)).scalar_one() == "medium"

    command.downgrade(config, "0006_checklist_configuration")
    assert "priority" not in {column["name"] for column in inspect(engine).get_columns("tasks")}
    engine.dispose()


def test_priority_migration_handles_database_with_legacy_0005_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "legacy-0005.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)

    metadata = MetaData()
    Table(
        "checklists",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(255), nullable=False),
        Column("description", Text, nullable=True),
        Column("assignee_count", Integer, nullable=False, default=1),
        Column("backlog_project_key_or_url", Text, nullable=True),
    )
    Table(
        "tasks",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("checklist_id", Integer, nullable=False),
        Column("title", String(255), nullable=False),
        Column("summary", Text, nullable=False),
        Column("estimated_hours", Float, nullable=False),
    )
    engine = create_engine(f"sqlite:///{database_path}")
    metadata.create_all(engine)
    command.stamp(config, "0005")

    command.upgrade(config, "0007_add_task_priority")

    task_columns = {column["name"]: column for column in inspect(engine).get_columns("tasks")}
    assert task_columns["summary"]["nullable"]
    assert "priority" in task_columns
    engine.dispose()
