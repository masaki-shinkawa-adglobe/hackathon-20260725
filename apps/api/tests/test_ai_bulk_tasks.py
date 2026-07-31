import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_session
from app.gemini import (
    GeminiTaskGenerator,
    GeminiConfigurationError,
    GeminiRequestError,
    GeminiResponseError,
    get_task_generator,
)
from app.main import app
from app.models import Base, Checklist, Task
from app.schemas import GeneratedTask


class StubGenerator:
    def __init__(self, result: list[GeneratedTask] | Exception) -> None:
        self.result = result

    async def generate_tasks(
        self, *, checklist_name: str, description: str | None
    ) -> list[GeneratedTask]:
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


async def create_checklist(session_factory: async_sessionmaker[AsyncSession]) -> Checklist:
    async with session_factory() as session:
        checklist = Checklist(name="月次決算業務")
        session.add(checklist)
        await session.commit()
        await session.refresh(checklist)
        return checklist


@pytest.mark.asyncio
async def test_creates_generated_tasks_for_existing_checklist(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist = await create_checklist(session_factory)
    app.dependency_overrides[get_task_generator] = lambda: StubGenerator(
        [
            GeneratedTask(title="仕訳を確認", summary="当月の仕訳を確認する", estimated_hours=2),
            GeneratedTask(title="試算表を作成", summary="試算表を出力する", estimated_hours=1.5),
        ]
    )

    response = client.post(
        "/checklists/ai-bulk-tasks",
        json={"checklist_id": checklist.id, "description": "月末処理を分解"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "checklist": {"id": checklist.id, "name": "月次決算業務"},
        "tasks": [
            {"id": 1, "checklist_id": checklist.id, "title": "仕訳を確認", "summary": "当月の仕訳を確認する", "estimated_hours": 2.0},
            {"id": 2, "checklist_id": checklist.id, "title": "試算表を作成", "summary": "試算表を出力する", "estimated_hours": 1.5},
        ],
    }
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Task)) == 2


def test_requires_checklist_id(client: TestClient) -> None:
    assert client.post("/checklists/ai-bulk-tasks", json={}).status_code == 422


def test_returns_not_found_before_gemini_configuration(client: TestClient) -> None:
    response = client.post("/checklists/ai-bulk-tasks", json={"checklist_id": 999})
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (GeminiResponseError("invalid"), "invalid_ai_response"),
        (GeminiRequestError("failed"), "gemini_request_failed"),
        (GeminiConfigurationError("missing"), "gemini_not_configured"),
    ],
)
async def test_gemini_failures_do_not_create_tasks(
    client: TestClient,
    session_factory: async_sessionmaker[AsyncSession],
    error: Exception,
    expected_code: str,
) -> None:
    checklist = await create_checklist(session_factory)
    app.dependency_overrides[get_task_generator] = lambda: StubGenerator(error)

    response = client.post("/checklists/ai-bulk-tasks", json={"checklist_id": checklist.id})

    assert response.status_code in (502, 503)
    assert response.json()["detail"]["code"] == expected_code
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Task)) == 0


@pytest.mark.asyncio
async def test_invalid_or_empty_ai_output_is_not_persisted(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist = await create_checklist(session_factory)
    app.dependency_overrides[get_task_generator] = lambda: StubGenerator([])

    response = client.post("/checklists/ai-bulk-tasks", json={"checklist_id": checklist.id})

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "invalid_ai_response"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Task)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("response_text", ["not json", "[]", '[{"title":"only title"}]'])
async def test_gemini_parser_rejects_invalid_responses(response_text: str) -> None:
    generator = GeminiTaskGenerator("test-key")
    generator._request = lambda _: response_text  # type: ignore[method-assign]

    with pytest.raises(GeminiResponseError):
        await generator.generate_tasks(checklist_name="月次決算業務", description=None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_text",
    [
        '[{"title":"工数が無限大","summary":"不正な工数","estimated_hours":Infinity}]',
        '[{"title":"工数が桁あふれ","summary":"不正な工数","estimated_hours":1e400}]',
    ],
)
async def test_non_finite_ai_hours_return_error_without_persisting_tasks(
    client: TestClient,
    session_factory: async_sessionmaker[AsyncSession],
    response_text: str,
) -> None:
    checklist = await create_checklist(session_factory)
    generator = GeminiTaskGenerator("test-key")
    generator._request = lambda _: response_text  # type: ignore[method-assign]
    app.dependency_overrides[get_task_generator] = lambda: generator

    response = client.post("/checklists/ai-bulk-tasks", json={"checklist_id": checklist.id})

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "invalid_ai_response"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Task)) == 0
