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
    session_factory: async_sessionmaker[AsyncSession], *, name: str = "月次決算", description: str | None = "概要",
    assignee_count: int = 1,
) -> Checklist:
    async with session_factory() as session:
        checklist = Checklist(name=name, description=description, assignee_count=assignee_count)
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


def test_checklist_configuration_migration_upgrade_and_downgrade() -> None:
    migration_path = Path(__file__).parents[1] / "migrations/versions/0005_add_checklist_configuration.py"
    spec = importlib.util.spec_from_file_location("migration_0005", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE checklists (id INTEGER PRIMARY KEY)")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        columns = {column["name"]: column for column in inspect(connection).get_columns("checklists")}
        assert set(columns) == {"id", "assignee_count", "backlog_project_key_or_url"}
        assert not columns["assignee_count"]["nullable"]
        assert columns["assignee_count"]["default"] == "1"
        assert columns["backlog_project_key_or_url"]["nullable"]
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert {column["name"] for column in inspect(connection).get_columns("checklists")} == {"id"}
    engine.dispose()


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


def test_checklist_get_response_openapi_schemas() -> None:
    schemas = app.openapi()["components"]["schemas"]
    list_item = schemas["ChecklistListItemResponse"]["properties"]
    detail = schemas["ChecklistDetailResponse"]["properties"]

    assert "assignee_count" in list_item
    assert list_item["backlog_last_registered_at"] == {
        "anyOf": [{"type": "string", "format": "date-time"}, {"type": "null"}],
        "title": "Backlog Last Registered At",
    }
    assert "backlog_registration" not in list_item
    assert "assignee_count" in detail
    assert "backlog_project_key_or_url" in detail
    assert "backlog_registration" in detail


@pytest.mark.asyncio
async def test_create_checklist_returns_created_checklist_and_persists_optional_values(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = client.post(
        "/checklists",
        json={
            "name": "リリース準備",
            "description": "",
            "backlog_project_key_or_url": "自由入力のプロジェクト情報",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "name": "リリース準備",
        "description": "",
        "backlog_project_key_or_url": "自由入力のプロジェクト情報",
    }
    async with session_factory() as session:
        checklist = await session.get(Checklist, 1)
        assert checklist is not None
        assert checklist.assignee_count == 1
        assert checklist.description == ""
        assert checklist.backlog_project_key_or_url == "自由入力のプロジェクト情報"


def test_create_checklist_allows_null_optional_values(client: TestClient) -> None:
    response = client.post("/checklists", json={"name": "下書き", "description": None})

    assert response.status_code == 201
    assert response.json()["description"] is None
    assert response.json()["backlog_project_key_or_url"] is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [("  ", None), (" PROJ ", " PROJ ")],
)
def test_create_checklist_normalizes_only_blank_backlog_project_value(
    client: TestClient, value: str, expected: str | None
) -> None:
    response = client.post("/checklists", json={"name": "下書き", "backlog_project_key_or_url": value})

    assert response.status_code == 201
    assert response.json()["backlog_project_key_or_url"] == expected


@pytest.mark.parametrize(
    "payload",
    [{}, {"name": ""}, {"name": "   "}, {"name": "a" * 256}],
)
def test_create_checklist_rejects_invalid_name(client: TestClient, payload: dict[str, str]) -> None:
    assert client.post("/checklists", json=payload).status_code == 422


@pytest.mark.asyncio
async def test_update_checklist_returns_updated_checklist_and_persists_values(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist = await add_checklist(session_factory)
    response = client.patch(
        f"/checklists/{checklist.id}",
        json={
            "name": "  月次決算（改訂）  ",
            "description": "",
            "assignee_count": 3,
            "backlog_project_key_or_url": "https://example.backlog.com/projects/PROJ",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": checklist.id,
        "name": "月次決算（改訂）",
        "description": None,
        "assignee_count": 3,
        "backlog_project_key_or_url": "https://example.backlog.com/projects/PROJ",
    }
    async with session_factory() as session:
        updated = await session.get(Checklist, checklist.id)
        assert updated is not None
        assert updated.assignee_count == 3
        assert updated.backlog_project_key_or_url == "https://example.backlog.com/projects/PROJ"
        assert updated.name == "月次決算（改訂）"
        assert updated.description is None


@pytest.mark.asyncio
async def test_update_checklist_preserves_omitted_optional_values(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist = await add_checklist(session_factory)
    async with session_factory() as session:
        persisted = await session.get(Checklist, checklist.id)
        assert persisted is not None
        persisted.assignee_count = 3
        persisted.backlog_project_key_or_url = "PROJ"
        await session.commit()

    response = client.patch(f"/checklists/{checklist.id}", json={"name": "更新後", "description": "説明"})

    assert response.status_code == 200
    assert response.json()["assignee_count"] == 3
    assert response.json()["backlog_project_key_or_url"] == "PROJ"


@pytest.mark.parametrize(
    ("value", "expected"),
    [("\t", None), (" https://example.backlog.com/projects/PROJ ", " https://example.backlog.com/projects/PROJ ")],
)
def test_update_checklist_normalizes_only_blank_backlog_project_value(
    client: TestClient, value: str, expected: str | None
) -> None:
    created = client.post("/checklists", json={"name": "更新対象"})

    response = client.patch(
        f"/checklists/{created.json()['id']}",
        json={"name": "更新後", "backlog_project_key_or_url": value},
    )

    assert response.status_code == 200
    assert response.json()["backlog_project_key_or_url"] == expected


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": "有効", "assignee_count": 0},
        {"name": "有効", "assignee_count": -1},
        {"name": "有効", "assignee_count": 1.0},
        {"name": "有効", "assignee_count": 1.5},
        {"name": "有効", "assignee_count": None},
        {"name": "   ", "assignee_count": 1},
    ],
)
def test_update_checklist_rejects_invalid_input(client: TestClient, payload: dict[str, object]) -> None:
    assert client.patch("/checklists/1", json=payload).status_code == 422


def test_update_checklist_returns_not_found(client: TestClient) -> None:
    response = client.patch("/checklists/999", json={"name": "有効", "assignee_count": 1})
    assert response.status_code == 404
    assert response.json() == {"detail": "Checklist not found"}


@pytest.mark.asyncio
async def test_delete_checklist_removes_local_records_without_response_body(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist = await add_checklist(session_factory)
    await add_backlog_link(session_factory, checklist.id)
    async with session_factory() as session:
        session.add(Task(checklist_id=checklist.id, title="ローカルタスク", summary="削除対象", estimated_hours=1))
        await session.commit()

    response = client.delete(f"/checklists/{checklist.id}")

    assert response.status_code == 204
    assert response.content == b""
    async with session_factory() as session:
        assert await session.get(Checklist, checklist.id) is None
        assert await session.scalar(select(Task).where(Task.checklist_id == checklist.id)) is None
        assert await session.scalar(
            select(ChecklistBacklogLink).where(ChecklistBacklogLink.checklist_id == checklist.id)
        ) is None


def test_delete_checklist_returns_not_found(client: TestClient) -> None:
    response = client.delete("/checklists/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Checklist not found"}


@pytest.mark.asyncio
async def test_list_checklists_includes_task_count_assignee_count_and_backlog_registration_time(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    registered = await add_checklist(session_factory, name="登録済み", assignee_count=3)
    unregistered = await add_checklist(session_factory, name="未登録", assignee_count=2)
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
    assert checklists[0]["assignee_count"] == 3
    assert checklists[0]["backlog_last_registered_at"] == link.registered_at.isoformat()
    assert "backlog_registration" not in checklists[0]
    assert checklists[1]["id"] == unregistered.id
    assert checklists[1]["task_count"] == 0
    assert checklists[1]["assignee_count"] == 2
    assert checklists[1]["backlog_last_registered_at"] is None
    assert "backlog_registration" not in checklists[1]


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
    checklist = await add_checklist(
        session_factory, description="月次決算の標準チェックリスト", assignee_count=3
    )
    link = await add_backlog_link(session_factory, checklist.id)
    async with session_factory() as session:
        session.add(Task(checklist_id=checklist.id, title="仕訳確認", summary="仕訳を確認する", estimated_hours=2))
        await session.commit()

    response = client.get(f"/checklists/{checklist.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": checklist.id, "name": "月次決算", "description": "月次決算の標準チェックリスト",
        "assignee_count": 3,
        "backlog_project_key_or_url": None,
        "backlog_registration": {
            "is_registered": True, "link_id": link.id, "backlog_issue_id": 12345,
            "backlog_issue_key": "PROJ-100", "backlog_issue_url": "https://example.backlog.com/view/PROJ-100",
        },
        "tasks": [{"id": 1, "checklist_id": checklist.id, "title": "仕訳確認", "summary": "仕訳を確認する", "estimated_hours": 2.0, "priority": "medium"}],
    }


@pytest.mark.asyncio
async def test_get_checklist_returns_empty_tasks_and_unregistered_values(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist = await add_checklist(session_factory, description=None)

    response = client.get(f"/checklists/{checklist.id}")

    assert response.status_code == 200
    assert response.json()["description"] is None
    assert response.json()["assignee_count"] == 1
    assert response.json()["backlog_project_key_or_url"] is None
    assert response.json()["tasks"] == []
    assert response.json()["backlog_registration"] == {
        "is_registered": False, "link_id": None, "backlog_issue_id": None,
        "backlog_issue_key": None, "backlog_issue_url": None,
    }


@pytest.mark.asyncio
async def test_get_checklist_returns_configured_backlog_project_value(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist = await add_checklist(session_factory)
    async with session_factory() as session:
        persisted = await session.get(Checklist, checklist.id)
        assert persisted is not None
        persisted.backlog_project_key_or_url = "PROJ"
        await session.commit()

    response = client.get(f"/checklists/{checklist.id}")

    assert response.status_code == 200
    assert response.json()["backlog_project_key_or_url"] == "PROJ"


def test_get_checklist_returns_not_found(client: TestClient) -> None:
    response = client.get("/checklists/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Checklist not found"}
