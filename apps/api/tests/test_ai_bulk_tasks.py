import os
from io import BytesIO
from unittest.mock import patch

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
    TaskSource,
    GeminiConfigurationError,
    GeminiRequestError,
    GeminiResponseError,
    get_task_generator,
)
from app.file_processing import MAX_UPLOAD_SIZE, FileValidationError, read_upload_with_limit
from app.main import app
from app.models import Base, Checklist, Task
from app.schemas import GeneratedTask


class StubGenerator:
    def __init__(self, result: list[GeneratedTask] | Exception) -> None:
        self.result = result

    async def generate_tasks(
        self, *, checklist_name: str, description: str | None = None, source: object | None = None
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
        checklist = Checklist(name="月次決算業務", description="月次決算の標準チェックリスト")
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
        files={
            "checklist_id": (None, str(checklist.id)),
            "description": (None, "月末処理を分解"),
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "checklist": {
            "id": checklist.id,
            "name": "月次決算業務",
            "description": "月次決算の標準チェックリスト",
        },
        "tasks": [
            {"id": 1, "checklist_id": checklist.id, "title": "仕訳を確認", "summary": "当月の仕訳を確認する", "estimated_hours": 2.0},
            {"id": 2, "checklist_id": checklist.id, "title": "試算表を作成", "summary": "試算表を出力する", "estimated_hours": 1.5},
        ],
    }
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Task)) == 2


def test_requires_checklist_id(client: TestClient) -> None:
    assert client.post(
        "/checklists/ai-bulk-tasks",
        files={"description": (None, "月末処理を分解")},
    ).status_code == 422


@pytest.mark.asyncio
async def test_rejects_json_content_type_without_persisting_tasks(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = client.post(
        "/checklists/ai-bulk-tasks",
        json={"checklist_id": 1, "description": "月末処理を分解"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Content-Type must be multipart/form-data"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Task)) == 0


@pytest.mark.asyncio
async def test_rejects_missing_description_and_file_without_persisting_tasks(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist = await create_checklist(session_factory)

    response = client.post(
        "/checklists/ai-bulk-tasks",
        files={"checklist_id": (None, str(checklist.id))},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Either description or file is required"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Task)) == 0


@pytest.mark.asyncio
async def test_rejects_blank_description_without_file_without_persisting_tasks(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist = await create_checklist(session_factory)

    response = client.post(
        "/checklists/ai-bulk-tasks",
        files={"checklist_id": (None, str(checklist.id)), "description": (None, "   ")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Either description or file is required"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Task)) == 0


@pytest.mark.asyncio
async def test_rejects_urlencoded_content_type_without_persisting_tasks(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = client.post(
        "/checklists/ai-bulk-tasks",
        data={"checklist_id": "1", "description": "月末処理を分解"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Content-Type must be multipart/form-data"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Task)) == 0


@pytest.mark.asyncio
async def test_rejects_invalid_json_content_type_without_persisting_tasks(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = client.post(
        "/checklists/ai-bulk-tasks",
        content=b'{"checklist_id":',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Content-Type must be multipart/form-data"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Task)) == 0


@pytest.mark.asyncio
async def test_invalid_utf8_json_returns_422_without_persisting_tasks(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = client.post(
        "/checklists/ai-bulk-tasks",
        content=b"\xff",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Content-Type must be multipart/form-data"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Task)) == 0


def test_ai_bulk_tasks_openapi_declares_multipart_request_body() -> None:
    request_body = app.openapi()["paths"]["/checklists/ai-bulk-tasks"]["post"]["requestBody"]
    content = request_body["content"]

    assert set(content) == {"multipart/form-data"}
    assert content["multipart/form-data"]["schema"]["required"] == ["checklist_id"]
    assert content["multipart/form-data"]["schema"]["properties"]["description"] == {
        "type": ["string", "null"],
        "maxLength": 10_000,
    }
    assert content["multipart/form-data"]["schema"]["properties"]["file"] == {
        "type": "string",
        "format": "binary",
    }


def test_returns_not_found_before_gemini_configuration(client: TestClient) -> None:
    response = client.post(
        "/checklists/ai-bulk-tasks",
        files={"checklist_id": (None, "999"), "description": (None, "月末処理を分解")},
    )
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

    response = client.post(
        "/checklists/ai-bulk-tasks",
        files={"checklist_id": (None, str(checklist.id)), "description": (None, "月末処理を分解")},
    )

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

    response = client.post(
        "/checklists/ai-bulk-tasks",
        files={"checklist_id": (None, str(checklist.id)), "description": (None, "月末処理を分解")},
    )

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "invalid_ai_response"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Task)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("response_text", ["not json", "[]", '[{"title":"only title"}]'])
async def test_gemini_parser_rejects_invalid_responses(response_text: str) -> None:
    generator = GeminiTaskGenerator("test-key")
    generator._request = lambda *_: response_text  # type: ignore[method-assign]

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
    generator._request = lambda *_: response_text  # type: ignore[method-assign]
    app.dependency_overrides[get_task_generator] = lambda: generator

    response = client.post(
        "/checklists/ai-bulk-tasks",
        files={"checklist_id": (None, str(checklist.id)), "description": (None, "月末処理を分解")},
    )

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "invalid_ai_response"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Task)) == 0


class CapturingGenerator(StubGenerator):
    def __init__(self) -> None:
        super().__init__([GeneratedTask(title="生成タスク", summary="ファイルから生成", estimated_hours=1)])
        self.description: str | None = None
        self.source: object | None = None

    async def generate_tasks(self, *, checklist_name: str, description: str | None = None, source: object | None = None) -> list[GeneratedTask]:
        self.description = description
        self.source = source
        return await super().generate_tasks(checklist_name=checklist_name, description=description, source=source)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "content_type", "content"),
    [
        ("source.pdf", "application/pdf", b"%PDF-1.7 example"),
        ("source.csv", "text/csv", "作業,担当\n確認,田中\n".encode()),
        ("source.txt", "text/plain", "月次処理を確認".encode()),
    ],
)
async def test_creates_tasks_from_supported_uploaded_files(
    client: TestClient,
    session_factory: async_sessionmaker[AsyncSession],
    filename: str,
    content_type: str,
    content: bytes,
) -> None:
    checklist = await create_checklist(session_factory)
    generator = CapturingGenerator()
    app.dependency_overrides[get_task_generator] = lambda: generator

    response = client.post(
        "/checklists/ai-bulk-tasks",
        data={"checklist_id": str(checklist.id)},
        files={"file": (filename, content, content_type)},
    )

    assert response.status_code == 200
    assert generator.source is not None
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Task)) == 1


@pytest.mark.asyncio
async def test_upload_accepts_description_as_instruction(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    checklist = await create_checklist(session_factory)
    generator = CapturingGenerator()
    app.dependency_overrides[get_task_generator] = lambda: generator

    response = client.post(
        "/checklists/ai-bulk-tasks",
        data={"checklist_id": str(checklist.id), "description": "PDFを参考に担当者別へ分解して"},
        files={"file": ("source.pdf", b"%PDF-1.7 example", "application/pdf")},
    )

    assert response.status_code == 200
    assert generator.description == "PDFを参考に担当者別へ分解して"
    assert generator.source is not None


@pytest.mark.asyncio
async def test_extracts_all_xlsx_worksheets_before_generating_tasks(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.active.title = "第一"
    workbook.active.append(["作業", "担当"])
    workbook.active.append(["確認", "田中"])
    workbook.create_sheet("第二").append(["承認", "佐藤"])
    buffer = BytesIO()
    workbook.save(buffer)
    checklist = await create_checklist(session_factory)
    generator = CapturingGenerator()
    app.dependency_overrides[get_task_generator] = lambda: generator

    response = client.post(
        "/checklists/ai-bulk-tasks",
        data={"checklist_id": str(checklist.id)},
        files={"file": ("source.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert response.status_code == 200
    assert "# Sheet: 第一" in generator.source.text  # type: ignore[union-attr]
    assert "# Sheet: 第二" in generator.source.text  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("data", "files", "expected_status"),
    [
        ({}, {"file": ("source.txt", b"ok", "text/plain")}, 422),
        ({"checklist_id": "1"}, {}, 422),
        ({"checklist_id": "1"}, {"file": ("source.exe", b"x", "application/octet-stream")}, 415),
        ({"checklist_id": "1"}, {"file": ("source.csv", b"\xff", "text/csv")}, 422),
        ({"checklist_id": "1"}, {"file": ("source.xlsx", b"not xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, 422),
        ({"checklist_id": "1"}, {"file": ("source.txt", b"x" * (10 * 1024 * 1024 + 1), "text/plain")}, 413),
    ],
)
def test_rejects_invalid_multipart_input(
    client: TestClient, data: dict[str, str], files: dict[str, tuple[str, bytes, str]], expected_status: int
) -> None:
    response = client.post("/checklists/ai-bulk-tasks", data=data, files=files)
    assert response.status_code == expected_status


def test_returns_not_found_for_uploaded_file_before_gemini(client: TestClient) -> None:
    response = client.post(
        "/checklists/ai-bulk-tasks",
        data={"checklist_id": "999"},
        files={"file": ("source.txt", b"task", "text/plain")},
    )
    assert response.status_code == 404


def test_gemini_sends_pdf_as_document_part() -> None:
    generator = GeminiTaskGenerator("test-key")
    with patch("google.genai.Client") as client_class:
        client_class.return_value.models.generate_content.return_value.text = "[]"
        generator._request(
            "prompt",
            TaskSource(document=b"%PDF-1.7", document_mime_type="application/pdf"),
        )

    contents = client_class.return_value.models.generate_content.call_args.kwargs["contents"]
    assert contents[0] == "prompt"
    assert contents[1].inline_data.mime_type == "application/pdf"
    assert contents[1].inline_data.data == b"%PDF-1.7"


@pytest.mark.asyncio
async def test_upload_read_stops_after_size_limit() -> None:
    class ChunkedUpload:
        def __init__(self, content: bytes) -> None:
            self.content = content
            self.position = 0

        async def read(self, size: int) -> bytes:
            chunk = self.content[self.position : self.position + size]
            self.position += len(chunk)
            return chunk

    upload = ChunkedUpload(b"x" * (MAX_UPLOAD_SIZE + 2))
    with pytest.raises(FileValidationError) as error:
        await read_upload_with_limit(upload)  # type: ignore[arg-type]

    assert error.value.status_code == 413
    assert upload.position == MAX_UPLOAD_SIZE + 1
