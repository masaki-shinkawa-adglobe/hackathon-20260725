import os
from collections.abc import AsyncIterator
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
import pytest_asyncio
from sqlalchemy import Column, Float, Integer, MetaData, String, Table, Text, create_engine, func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_session
from app.main import app
from app.models import Base, Checklist, Task
from app.schemas import GeneratedTask


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


async def create_checklist(session_factory: async_sessionmaker[AsyncSession]) -> Checklist:
    async with session_factory() as session:
        checklist = Checklist(name="月次決算業務")
        session.add(checklist)
        await session.commit()
        await session.refresh(checklist)
        return checklist


@pytest.mark.asyncio
async def test_creates_manual_task_with_normalized_values(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist = await create_checklist(session_factory)

    response = client.post(
        f"/checklists/{checklist.id}/tasks",
        json={"title": "  仕訳を確認  ", "summary": "   ", "estimated_hours": 1.5},
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "checklist_id": checklist.id,
        "title": "仕訳を確認",
        "summary": None,
        "estimated_hours": 1.5,
    }
    async with session_factory() as session:
        task = await session.scalar(select(Task))
        assert task is not None
        assert (task.title, task.summary, task.estimated_hours) == ("仕訳を確認", None, 1.5)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"title": "   ", "summary": None, "estimated_hours": 1},
        {"title": "x" * 256, "summary": None, "estimated_hours": 1},
        {"title": "valid", "summary": None, "estimated_hours": 0},
        {"title": "valid", "summary": None, "estimated_hours": -1},
        {"title": "valid", "summary": None, "estimated_hours": "Infinity"},
    ],
)
async def test_rejects_invalid_manual_task_without_persisting(
    client: TestClient,
    session_factory: async_sessionmaker[AsyncSession],
    payload: dict[str, object],
) -> None:
    checklist = await create_checklist(session_factory)

    response = client.post(f"/checklists/{checklist.id}/tasks", json=payload)

    assert response.status_code == 422
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Task)) == 0


@pytest.mark.asyncio
async def test_manual_task_returns_not_found_without_persisting(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = client.post(
        "/checklists/999/tasks",
        json={"title": "仕訳を確認", "summary": "確認内容", "estimated_hours": 1},
    )

    assert response.status_code == 404
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Task)) == 0


def test_manual_task_openapi_schema() -> None:
    operation = app.openapi()["paths"]["/checklists/{checklist_id}/tasks"]["post"]

    assert operation["responses"]["201"]["description"] == "Successful Response"
    schema = app.openapi()["components"]["schemas"]["ManualTaskCreateRequest"]
    assert schema["required"] == ["title", "estimated_hours"]
    assert schema["properties"]["title"]["minLength"] == 1
    assert schema["properties"]["title"]["maxLength"] == 255
    assert schema["properties"]["estimated_hours"]["exclusiveMinimum"] == 0.0
    with pytest.raises(ValueError):
        GeneratedTask.model_validate({"title": "AI task", "summary": "", "estimated_hours": 1})


def test_summary_nullable_migration_upgrade_and_downgrade(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_path = tmp_path / "migration.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)

    command.stamp(config, "0004")
    metadata = MetaData()
    Table("checklists", metadata, Column("id", Integer, primary_key=True), Column("name", String(255), nullable=False))
    tasks = Table(
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

    command.upgrade(config, "0005")
    assert inspect(engine).get_columns("tasks")[3]["nullable"] is True
    with engine.begin() as connection:
        connection.execute(tasks.insert(), {"checklist_id": 1, "title": "手動", "summary": None, "estimated_hours": 1})

    command.downgrade(config, "0004")
    assert inspect(engine).get_columns("tasks")[3]["nullable"] is False
    with engine.connect() as connection:
        assert connection.execute(select(tasks.c.summary)).scalar_one() == ""
    engine.dispose()
