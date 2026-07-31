import importlib.util
import os
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
import pytest_asyncio
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_session
from app.main import app
from app.models import Base, Checklist, ChecklistBacklogLink, Task


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


async def add_checklist(
    session_factory: async_sessionmaker[AsyncSession], *, name: str = "月次決算", description: str | None = "概要"
) -> Checklist:
    async with session_factory() as session:
        checklist = Checklist(name=name, description=description)
        session.add(checklist)
        await session.commit()
        await session.refresh(checklist)
        return checklist


async def add_backlog_link(session_factory: async_sessionmaker[AsyncSession], checklist_id: int) -> ChecklistBacklogLink:
    async with session_factory() as session:
        link = ChecklistBacklogLink(
            checklist_id=checklist_id,
            backlog_issue_id=12345,
            backlog_issue_key="PROJ-100",
            backlog_issue_url="https://example.backlog.com/view/PROJ-100",
        )
        session.add(link)
        await session.commit()
        await session.refresh(link)
        return link


def test_backlog_link_migration_upgrade_and_downgrade() -> None:
    migration_path = Path(__file__).parents[1] / "migrations/versions/0004_add_checklist_backlog_links.py"
    spec = importlib.util.spec_from_file_location("migration_0004", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE checklists (id INTEGER PRIMARY KEY)")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        inspector = inspect(connection)
        assert "checklist_backlog_links" in inspector.get_table_names()
        columns = {column["name"]: column for column in inspector.get_columns("checklist_backlog_links")}
        assert set(columns) == {
            "id", "checklist_id", "backlog_issue_id", "backlog_issue_key", "backlog_issue_url", "registered_at"
        }
        assert not columns["checklist_id"]["nullable"]
        assert inspector.get_foreign_keys("checklist_backlog_links")[0]["options"]["ondelete"] == "CASCADE"
        assert any(constraint["column_names"] == ["checklist_id"] for constraint in inspector.get_unique_constraints("checklist_backlog_links"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert "checklist_backlog_links" not in inspect(connection).get_table_names()
    engine.dispose()


@pytest.mark.asyncio
async def test_backlog_link_is_unique_and_deleted_with_checklist(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    checklist = await add_checklist(session_factory)
    await add_backlog_link(session_factory, checklist.id)
    async with session_factory() as session:
        session.add(ChecklistBacklogLink(checklist_id=checklist.id, backlog_issue_id=2, backlog_issue_key="PROJ-2", backlog_issue_url="https://example.test/2"))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
        checklist_to_delete = await session.get(Checklist, checklist.id)
        assert checklist_to_delete is not None
        await session.delete(checklist_to_delete)
        await session.commit()
        assert await session.scalar(select(ChecklistBacklogLink).where(ChecklistBacklogLink.checklist_id == checklist.id)) is None


def test_list_checklists_returns_empty(client: TestClient) -> None:
    assert client.get("/checklists").json() == {"checklists": []}


@pytest.mark.asyncio
async def test_list_checklists_includes_task_count_and_registration(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    registered = await add_checklist(session_factory, name="登録済み")
    unregistered = await add_checklist(session_factory, name="未登録")
    link = await add_backlog_link(session_factory, registered.id)
    async with session_factory() as session:
        session.add_all([
            Task(checklist_id=registered.id, title="確認", summary="確認する", estimated_hours=2),
            Task(checklist_id=registered.id, title="承認", summary="承認する", estimated_hours=1.5),
        ])
        await session.commit()

    response = client.get("/checklists")

    assert response.status_code == 200
    checklists = response.json()["checklists"]
    assert checklists[0]["id"] == registered.id
    assert checklists[0]["name"] == "登録済み"
    assert checklists[0]["task_count"] == 2
    assert checklists[0]["backlog_registration"] == {
        "is_registered": True, "link_id": link.id, "backlog_issue_id": 12345,
        "backlog_issue_key": "PROJ-100", "backlog_issue_url": "https://example.backlog.com/view/PROJ-100",
    }
    assert checklists[1]["id"] == unregistered.id
    assert checklists[1]["task_count"] == 0
    assert checklists[1]["backlog_registration"] == {
        "is_registered": False, "link_id": None, "backlog_issue_id": None,
        "backlog_issue_key": None, "backlog_issue_url": None,
    }


@pytest.mark.asyncio
async def test_list_checklists_uses_one_query_regardless_of_checklist_count(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await add_checklist(session_factory, name="一件目")
    await add_checklist(session_factory, name="二件目")
    statements: list[str] = []
    engine = session_factory.kw["bind"].sync_engine

    def record_statement(*args: object) -> None:
        statements.append(args[2])  # type: ignore[arg-type]

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        response = client.get("/checklists")
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)

    assert response.status_code == 200
    assert len(statements) == 1


@pytest.mark.asyncio
async def test_get_checklist_returns_detail_tasks_and_registration(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist = await add_checklist(session_factory, description="月次決算の標準チェックリスト")
    link = await add_backlog_link(session_factory, checklist.id)
    async with session_factory() as session:
        session.add(Task(checklist_id=checklist.id, title="仕訳確認", summary="仕訳を確認する", estimated_hours=2))
        await session.commit()

    response = client.get(f"/checklists/{checklist.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": checklist.id, "name": "月次決算", "description": "月次決算の標準チェックリスト",
        "backlog_registration": {
            "is_registered": True, "link_id": link.id, "backlog_issue_id": 12345,
            "backlog_issue_key": "PROJ-100", "backlog_issue_url": "https://example.backlog.com/view/PROJ-100",
        },
        "tasks": [{"id": 1, "checklist_id": checklist.id, "title": "仕訳確認", "summary": "仕訳を確認する", "estimated_hours": 2.0}],
    }


@pytest.mark.asyncio
async def test_get_checklist_returns_empty_tasks_and_unregistered_values(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist = await add_checklist(session_factory, description=None)

    response = client.get(f"/checklists/{checklist.id}")

    assert response.status_code == 200
    assert response.json()["description"] is None
    assert response.json()["tasks"] == []
    assert response.json()["backlog_registration"] == {
        "is_registered": False, "link_id": None, "backlog_issue_id": None,
        "backlog_issue_key": None, "backlog_issue_url": None,
    }


def test_get_checklist_returns_not_found(client: TestClient) -> None:
    response = client.get("/checklists/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Checklist not found"}
