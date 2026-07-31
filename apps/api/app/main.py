from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
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
from app.models import Checklist, ChecklistBacklogLink, Task
from app.file_processing import FileValidationError, process_upload, read_upload_with_limit
from app.schemas import (
    AIBulkTasksResponse,
    AIBulkTasksUploadRequest,
    BacklogRegistrationResponse,
    ChecklistDetailResponse,
    ChecklistCreateRequest,
    ChecklistCreateResponse,
    ChecklistListItemResponse,
    ChecklistUpdateRequest,
    ChecklistUpdateResponse,
    ChecklistsResponse,
    ManualTaskCreateRequest,
    TaskResponse,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)


def backlog_registration(link: ChecklistBacklogLink | None) -> BacklogRegistrationResponse:
    if link is None:
        return BacklogRegistrationResponse(
            is_registered=False,
            link_id=None,
            backlog_issue_id=None,
            backlog_issue_key=None,
            backlog_issue_url=None,
        )
    return BacklogRegistrationResponse(
        is_registered=True,
        link_id=link.id,
        backlog_issue_id=link.backlog_issue_id,
        backlog_issue_key=link.backlog_issue_key,
        backlog_issue_url=link.backlog_issue_url,
    )


@app.get("/health")
async def health(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post(
    "/checklists", status_code=status.HTTP_201_CREATED, response_model=ChecklistCreateResponse
)
async def create_checklist(
    request: ChecklistCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Checklist:
    checklist = Checklist(**request.model_dump())
    session.add(checklist)
    await session.commit()
    await session.refresh(checklist)
    return checklist


@app.get("/checklists", response_model=ChecklistsResponse)
async def list_checklists(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChecklistsResponse:
    task_counts = (
        select(Task.checklist_id, func.count(Task.id).label("task_count"))
        .group_by(Task.checklist_id)
        .subquery()
    )
    result = await session.execute(
        select(Checklist, task_counts.c.task_count, ChecklistBacklogLink)
        .outerjoin(task_counts, task_counts.c.checklist_id == Checklist.id)
        .outerjoin(ChecklistBacklogLink, ChecklistBacklogLink.checklist_id == Checklist.id)
        .order_by(Checklist.id)
    )
    return ChecklistsResponse(
        checklists=[
            ChecklistListItemResponse(
                id=checklist.id,
                name=checklist.name,
                task_count=task_count or 0,
                backlog_registration=backlog_registration(link),
                updated_at=checklist.updated_at,
            )
            for checklist, task_count, link in result.all()
        ]
    )


@app.patch("/checklists/{checklist_id}", response_model=ChecklistUpdateResponse)
async def update_checklist(
    checklist_id: int,
    request: ChecklistUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Checklist:
    checklist = await session.get(Checklist, checklist_id)
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist not found")

    for field, value in request.model_dump().items():
        setattr(checklist, field, value)
    await session.commit()
    await session.refresh(checklist)
    return checklist


@app.delete("/checklists/{checklist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_checklist(
    checklist_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    checklist = await session.get(Checklist, checklist_id)
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist not found")

    await session.delete(checklist)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/checklists/{checklist_id}", response_model=ChecklistDetailResponse)
async def get_checklist(
    checklist_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChecklistDetailResponse:
    checklist = await session.scalar(
        select(Checklist)
        .options(joinedload(Checklist.backlog_link), selectinload(Checklist.tasks))
        .where(Checklist.id == checklist_id)
    )
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist not found")
    return ChecklistDetailResponse(
        id=checklist.id,
        name=checklist.name,
        description=checklist.description,
        backlog_registration=backlog_registration(checklist.backlog_link),
        tasks=checklist.tasks,
    )


@app.post(
    "/checklists/{checklist_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_task(
    checklist_id: int,
    task_request: ManualTaskCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TaskResponse:
    checklist = await session.scalar(select(Checklist).where(Checklist.id == checklist_id))
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist not found")

    task = Task(
        checklist_id=checklist.id,
        title=task_request.title,
        summary=task_request.summary,
        estimated_hours=task_request.estimated_hours,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


@app.post(
    "/checklists/ai-bulk-tasks",
    response_model=AIBulkTasksResponse,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["checklist_id"],
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
    source: TaskSource | None = None
    try:
        if not content_type.startswith("multipart/form-data"):
            raise HTTPException(status_code=422, detail="Content-Type must be multipart/form-data")

        form = await request.form()
        upload_values = form.getlist("file")
        if len(upload_values) > 1:
            raise HTTPException(status_code=422, detail="A single file is allowed")
        upload_request = AIBulkTasksUploadRequest.model_validate(
            {"checklist_id": form.get("checklist_id"), "description": form.get("description")}
        )
        checklist_id = upload_request.checklist_id
        description = upload_request.description
        if upload_values:
            if not isinstance(upload_values[0], UploadFile):
                raise HTTPException(status_code=422, detail="File must be an upload")
            upload = upload_values[0]
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

        if description is None and source is None:
            raise HTTPException(status_code=422, detail="Either description or file is required")
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error
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
