import os
from collections.abc import AsyncIterator

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_session
from app.gemini import GeminiConfigurationError, GeminiRequestError, get_schedule_generator
from app.main import app
from app.models import BacklogPlan, BacklogPlanItem, Base, Checklist, Task, TaskBacklogLink
from app.schemas import GeneratedScheduleItem


class StubScheduleGenerator:
    def __init__(self, result: list[GeneratedScheduleItem] | Exception) -> None:
        self.result = result

    async def generate_schedule(self, **_: object) -> list[GeneratedScheduleItem]:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


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


async def create_tasks(session_factory: async_sessionmaker[AsyncSession]) -> tuple[Checklist, list[Task]]:
    async with session_factory() as session:
        checklist = Checklist(name="日程計画")
        tasks = [
            Task(checklist=checklist, title="確認", summary="要件を確認", estimated_hours=8),
            Task(checklist=checklist, title="実装", summary="実装する", estimated_hours=16),
        ]
        session.add_all(tasks)
        await session.commit()
        await session.refresh(checklist)
        for task in tasks:
            await session.refresh(task)
        return checklist, tasks


def request_body(tasks: list[Task]) -> dict[str, object]:
    return {
        "task_ids": [task.id for task in tasks],
        "start_date": "2026-08-03",
        "end_date": "2026-08-07",
        "expected_assignee_count": 1,
    }


@pytest.mark.asyncio
async def test_rejects_invalid_plan_input(client: TestClient, session_factory: async_sessionmaker[AsyncSession]) -> None:
    checklist, tasks = await create_tasks(session_factory)
    response = client.post(
        f"/checklists/{checklist.id}/backlog-plans",
        json={**request_body(tasks), "task_ids": [tasks[0].id, tasks[0].id]},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_creates_validated_backlog_plan(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist, tasks = await create_tasks(session_factory)
    app.dependency_overrides[get_schedule_generator] = lambda: StubScheduleGenerator([
        GeneratedScheduleItem(task_id=tasks[0].id, assignee_slot=1, start_date="2026-08-03", due_date="2026-08-03", depends_on_task_ids=[]),
        GeneratedScheduleItem(task_id=tasks[1].id, assignee_slot=1, start_date="2026-08-04", due_date="2026-08-05", depends_on_task_ids=[tasks[0].id]),
    ])

    response = client.post(f"/checklists/{checklist.id}/backlog-plans", json=request_body(tasks))

    assert response.status_code == 201
    assert response.json()["status"] == "planned"
    assert [item["task_id"] for item in response.json()["items"]] == [task.id for task in tasks]
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(BacklogPlan)) == 1
        assert await session.scalar(select(func.count()).select_from(BacklogPlanItem)) == 2


@pytest.mark.asyncio
async def test_rejects_issued_tasks_and_impossible_capacity_before_ai(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist, tasks = await create_tasks(session_factory)
    async with session_factory() as session:
        session.add(TaskBacklogLink(task_id=tasks[0].id, backlog_issue_id=1, backlog_issue_key="X-1", backlog_issue_url="https://example.test/X-1"))
        await session.commit()

    issued_response = client.post(f"/checklists/{checklist.id}/backlog-plans", json=request_body(tasks))
    assert issued_response.status_code == 409
    assert issued_response.json()["detail"]["code"] == "task_already_issued"

    capacity_response = client.post(
        f"/checklists/{checklist.id}/backlog-plans",
        json={**request_body(tasks), "task_ids": [tasks[1].id], "start_date": "2026-08-08", "end_date": "2026-08-09"},
    )
    assert capacity_response.status_code == 422
    assert capacity_response.json()["detail"]["code"] == "schedule_impossible"


@pytest.mark.asyncio
@pytest.mark.parametrize("schedule", [
    lambda tasks: [GeneratedScheduleItem(task_id=tasks[0].id, assignee_slot=2, start_date="2026-08-03", due_date="2026-08-03")],
    lambda tasks: [
        GeneratedScheduleItem(task_id=tasks[0].id, assignee_slot=1, start_date="2026-08-03", due_date="2026-08-03", depends_on_task_ids=[tasks[1].id]),
        GeneratedScheduleItem(task_id=tasks[1].id, assignee_slot=1, start_date="2026-08-04", due_date="2026-08-05", depends_on_task_ids=[tasks[0].id]),
    ],
])
async def test_rejects_invalid_ai_schedule_without_persisting(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession], schedule: object
) -> None:
    checklist, tasks = await create_tasks(session_factory)
    app.dependency_overrides[get_schedule_generator] = lambda: StubScheduleGenerator(schedule(tasks))  # type: ignore[operator]

    response = client.post(f"/checklists/{checklist.id}/backlog-plans", json=request_body(tasks))
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "invalid_ai_schedule"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(BacklogPlan)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (GeminiConfigurationError("GEMINI_API_KEY=secret-value"), 503, "integration_not_configured"),
        (GeminiRequestError("GEMINI_API_KEY=secret-value"), 502, "gemini_request_failed"),
    ],
)
async def test_gemini_errors_do_not_expose_secrets_or_persist(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession], error: Exception, status_code: int, code: str
) -> None:
    checklist, tasks = await create_tasks(session_factory)
    app.dependency_overrides[get_schedule_generator] = lambda: StubScheduleGenerator(error)

    response = client.post(f"/checklists/{checklist.id}/backlog-plans", json=request_body(tasks))
    assert response.status_code == status_code
    assert response.json()["detail"]["code"] == code
    assert "secret-value" not in response.text
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(BacklogPlan)) == 0
