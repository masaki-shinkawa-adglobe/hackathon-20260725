import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_session
from app.main import app
from app.models import Base, Checklist, Task
from app.seed import SEED_CHECKLISTS, seed


@pytest_asyncio.fixture
async def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def client(session_factory: async_sessionmaker[AsyncSession]) -> TestClient:
    async def override_session() -> AsyncSession:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_seed_data_contains_multiple_checklists_and_twenty_tasks() -> None:
    assert len(SEED_CHECKLISTS) >= 2
    tasks = [task for checklist in SEED_CHECKLISTS for task in checklist["tasks"]]
    assert len(tasks) == 20
    assert {task[3] for task in tasks if task[3] is not None} == {"low", "medium", "high"}
    assert any(task[3] is None for task in tasks)
    assert all(task[0] and task[1] and task[2] > 0 for task in tasks)


@pytest.mark.asyncio
async def test_seed_creates_pilot_data_and_can_be_verified_through_api(
    session_factory: async_sessionmaker[AsyncSession],
    client: TestClient,
) -> None:
    assert await seed(session_factory) is True

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Checklist)) == 3
        assert await session.scalar(select(func.count()).select_from(Task)) == 20
        priorities = set((await session.scalars(select(Task.priority))).all())
        assert priorities == {"low", "medium", "high"}
        assert await session.scalar(
            select(Task.priority).where(Task.title == "担当者へ確認")
        ) == "medium"

    listed = client.get("/checklists")
    assert listed.status_code == 200
    assert len(listed.json()["checklists"]) == 3
    checklist_id = listed.json()["checklists"][0]["id"]
    detail = client.get(f"/checklists/{checklist_id}")
    assert detail.status_code == 200
    assert detail.json()["tasks"]
    assert {task["priority"] for task in detail.json()["tasks"]} <= {"low", "medium", "high"}


@pytest.mark.asyncio
async def test_seed_is_idempotent_and_preserves_existing_data(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        session.add(Checklist(name="利用者が作成したチェックリスト"))
        await session.commit()

    assert await seed(session_factory) is True
    assert await seed(session_factory) is False

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Checklist)) == 4
        assert await session.scalar(select(func.count()).select_from(Task)) == 20
        existing = await session.scalar(
            select(Checklist).where(Checklist.name == "利用者が作成したチェックリスト")
        )
        assert existing is not None
