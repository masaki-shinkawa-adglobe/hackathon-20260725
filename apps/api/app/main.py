from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from json import JSONDecodeError
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.database import engine, get_session
from app.gemini import (
    GeminiConfigurationError,
    GeminiRequestError,
    GeminiResponseError,
    TaskGenerator,
    TaskSource,
    get_task_generator,
)
from app.models import Checklist, Task
from app.file_processing import FileValidationError, process_upload, read_upload_with_limit
from app.schemas import AIBulkTasksRequest, AIBulkTasksResponse, AIBulkTasksUploadRequest


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post(
    "/checklists/ai-bulk-tasks",
    response_model=AIBulkTasksResponse,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["checklist_id"],
                        "properties": {
                            "checklist_id": {"type": "integer"},
                            "description": {"type": ["string", "null"], "maxLength": 10_000},
                        },
                    }
                },
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["checklist_id", "file"],
                        "properties": {
                            "checklist_id": {"type": "integer"},
                            "description": {"type": ["string", "null"], "maxLength": 10_000},
                            "file": {"type": "string", "format": "binary"},
                        },
                    }
                },
            },
        }
    },
)
async def create_ai_bulk_tasks(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    task_generator: Annotated[TaskGenerator, Depends(get_task_generator)],
) -> AIBulkTasksResponse:
    content_type = request.headers.get("content-type", "").lower()
    description: str | None = None
    source: TaskSource | None = None
    try:
        if content_type.startswith("multipart/form-data"):
            form = await request.form()
            upload_values = form.getlist("file")
            if len(upload_values) != 1 or not isinstance(upload_values[0], UploadFile):
                raise HTTPException(status_code=422, detail="A single file is required")
            upload = upload_values[0]
            upload_request = AIBulkTasksUploadRequest.model_validate(
                {"checklist_id": form.get("checklist_id"), "description": form.get("description")}
            )
            processed = process_upload(
                filename=upload.filename,
                content_type=upload.content_type,
                data=await read_upload_with_limit(upload),
            )
            source = TaskSource(
                text=processed.text,
                document=processed.document,
                document_mime_type=processed.mime_type,
            )
            checklist_id = upload_request.checklist_id
            description = upload_request.description
        elif content_type.startswith("application/json"):
            json_request = AIBulkTasksRequest.model_validate(await request.json())
            checklist_id = json_request.checklist_id
            description = json_request.description
        else:
            raise HTTPException(status_code=422, detail="Content-Type must be application/json or multipart/form-data")
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error
    except (JSONDecodeError, UnicodeDecodeError) as error:
        raise RequestValidationError(
            [
                {
                    "type": "json_invalid",
                    "loc": ("body", getattr(error, "pos", getattr(error, "start", 0))),
                    "msg": "JSON decode error",
                    "input": {},
                    "ctx": {"error": str(error)},
                }
            ]
        ) from error
    except FileValidationError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error

    checklist = await session.scalar(
        select(Checklist).where(Checklist.id == checklist_id)
    )
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist not found")

    try:
        generated_tasks = await task_generator.generate_tasks(
            checklist_name=checklist.name, description=description, source=source
        )
        if not generated_tasks:
            raise GeminiResponseError("Gemini returned an empty task list")
    except GeminiConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "gemini_not_configured", "message": str(error)},
        ) from error
    except GeminiRequestError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "gemini_request_failed", "message": str(error)},
        ) from error
    except GeminiResponseError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "invalid_ai_response", "message": str(error)},
        ) from error

    tasks = [
        Task(
            checklist_id=checklist.id,
            title=generated.title,
            summary=generated.summary,
            estimated_hours=generated.estimated_hours,
        )
        for generated in generated_tasks
    ]
    session.add_all(tasks)
    await session.commit()
    for task in tasks:
        await session.refresh(task)
    return AIBulkTasksResponse(checklist=checklist, tasks=tasks)
