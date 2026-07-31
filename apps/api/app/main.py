from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from math import ceil
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.datastructures import UploadFile

from app.database import engine, get_session
from app.gemini import (
    GeminiConfigurationError,
    GeminiRequestError,
    GeminiResponseError,
    ScheduleGenerator,
    TaskGenerator,
    TaskSource,
    get_schedule_generator,
    get_task_generator,
)
from app.models import BacklogPlan, BacklogPlanItem, Checklist, Task, TaskBacklogLink
from app.file_processing import FileValidationError, process_upload, read_upload_with_limit
from app.schemas import (
    AIBulkTasksResponse,
    AIBulkTasksUploadRequest,
    BacklogPlanCreateRequest,
    BacklogPlanCreateResponse,
    BacklogPlanItemResponse,
    BacklogRegistrationResponse,
    ChecklistDetailResponse,
    ChecklistCreateRequest,
    ChecklistCreateResponse,
    ChecklistListItemResponse,
    ChecklistUpdateRequest,
    ChecklistUpdateResponse,
    ChecklistsResponse,
    GeneratedScheduleItem,
    ManualTaskCreateRequest,
    TaskDetailResponse,
    TaskResponse,
    TaskUpdateRequest,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)


def backlog_registration(
    issued_task_count: int, total_task_count: int, last_issued_at: datetime | None
) -> BacklogRegistrationResponse:
    if issued_task_count == 0:
        registration_status = "unregistered"
    elif issued_task_count == total_task_count:
        registration_status = "registered"
    else:
        registration_status = "partial"
    return BacklogRegistrationResponse(
        status=registration_status,
        issued_task_count=issued_task_count,
        total_task_count=total_task_count,
        last_issued_at=last_issued_at,
    )


def is_business_day(value: date) -> bool:
    return value.weekday() < 5


def business_day_count(start_date: date, end_date: date) -> int:
    return sum(
        is_business_day(start_date + timedelta(days=offset))
        for offset in range((end_date - start_date).days + 1)
    )


def next_business_day(value: date) -> date:
    result = value + timedelta(days=1)
    while not is_business_day(result):
        result += timedelta(days=1)
    return result


def schedule_error(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={"code": "invalid_ai_schedule", "message": message})


def validate_schedule(
    generated_items: list[GeneratedScheduleItem],
    tasks: list[Task],
    request: BacklogPlanCreateRequest,
) -> None:
    task_by_id = {task.id: task for task in tasks}
    if len(generated_items) != len(tasks):
        raise schedule_error("Gemini returned an incomplete schedule")
    items_by_task_id = {}
    for item in generated_items:
        task_id = item.task_id
        if task_id not in task_by_id or task_id in items_by_task_id:
            raise schedule_error("Gemini returned unexpected tasks")
        items_by_task_id[task_id] = item
        if not 1 <= item.assignee_slot <= request.expected_assignee_count:
            raise schedule_error("Gemini returned an invalid assignee slot")
        if not (request.start_date <= item.start_date <= item.due_date <= request.end_date):
            raise schedule_error("Gemini returned dates outside the requested range")
        if not is_business_day(item.start_date) or not is_business_day(item.due_date):
            raise schedule_error("Gemini scheduled a task on a non-business day")
        required_days = ceil(task_by_id[task_id].estimated_hours / 8)
        if business_day_count(item.start_date, item.due_date) != required_days:
            raise schedule_error("Gemini returned an invalid task duration")
        dependencies = item.depends_on_task_ids
        if len(dependencies) != len(set(dependencies)) or task_id in dependencies or not set(dependencies) <= set(task_by_id):
            raise schedule_error("Gemini returned invalid dependencies")

    for first in generated_items:
        for second in generated_items:
            if first is second or first.assignee_slot != second.assignee_slot:
                continue
            if first.start_date <= second.due_date and second.start_date <= first.due_date:
                raise schedule_error("Gemini returned overlapping assignee schedules")

    for task_id, item in items_by_task_id.items():
        for dependency_id in item.depends_on_task_ids:
            if item.start_date < next_business_day(items_by_task_id[dependency_id].due_date):
                raise schedule_error("Gemini returned an invalid dependency order")

    visiting: set[int] = set()
    visited: set[int] = set()

    def visit(task_id: int) -> None:
        if task_id in visiting:
            raise schedule_error("Gemini returned cyclic dependencies")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency_id in items_by_task_id[task_id].depends_on_task_ids:
            visit(dependency_id)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in items_by_task_id:
        visit(task_id)


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
    registration_summary = (
        select(
            Task.checklist_id,
            func.count(Task.id).label("task_count"),
            func.count(TaskBacklogLink.id).label("issued_task_count"),
            func.max(TaskBacklogLink.issued_at).label("last_issued_at"),
        )
        .outerjoin(TaskBacklogLink, TaskBacklogLink.task_id == Task.id)
        .group_by(Task.checklist_id)
        .subquery()
    )
    result = await session.execute(
        select(
            Checklist,
            registration_summary.c.task_count,
            registration_summary.c.issued_task_count,
            registration_summary.c.last_issued_at,
        )
        .outerjoin(registration_summary, registration_summary.c.checklist_id == Checklist.id)
        .order_by(Checklist.id)
    )
    return ChecklistsResponse(
        checklists=[
            ChecklistListItemResponse(
                id=checklist.id,
                name=checklist.name,
                task_count=task_count or 0,
                assignee_count=checklist.assignee_count,
                backlog_registration=backlog_registration(
                    issued_task_count or 0, task_count or 0, last_issued_at
                ),
                updated_at=checklist.updated_at,
            )
            for checklist, task_count, issued_task_count, last_issued_at in result.all()
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

    for field, value in request.model_dump(exclude_unset=True).items():
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
        select(Checklist).options(selectinload(Checklist.tasks).selectinload(Task.backlog_link))
        .where(Checklist.id == checklist_id)
    )
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist not found")
    return ChecklistDetailResponse(
        id=checklist.id,
        name=checklist.name,
        description=checklist.description,
        assignee_count=checklist.assignee_count,
        backlog_registration=backlog_registration(
            sum(task.backlog_link is not None for task in checklist.tasks),
            len(checklist.tasks),
            max(
                (task.backlog_link.issued_at for task in checklist.tasks if task.backlog_link is not None),
                default=None,
            ),
        ),
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


@app.get(
    "/checklists/{checklist_id}/tasks/{task_id}",
    response_model=TaskDetailResponse,
)
async def get_task(
    checklist_id: int,
    task_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TaskDetailResponse:
    result = await session.execute(
        select(Task, Checklist.name)
        .join(Checklist, Checklist.id == Task.checklist_id)
        .where(Task.id == task_id, Task.checklist_id == checklist_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    task, checklist_name = row
    return TaskDetailResponse(checklist_name=checklist_name, task=TaskResponse.model_validate(task))


@app.patch(
    "/checklists/{checklist_id}/tasks/{task_id}",
    response_model=TaskResponse,
)
async def update_task(
    checklist_id: int,
    task_id: int,
    request: TaskUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Task:
    task = await session.scalar(
        select(Task).where(Task.id == task_id, Task.checklist_id == checklist_id)
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    for field, value in request.model_dump().items():
        setattr(task, field, value)
    await session.commit()
    await session.refresh(task)
    return task


@app.post(
    "/checklists/{checklist_id}/backlog-plans",
    response_model=BacklogPlanCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_backlog_plan(
    checklist_id: int,
    request: BacklogPlanCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    schedule_generator: Annotated[ScheduleGenerator, Depends(get_schedule_generator)],
) -> BacklogPlanCreateResponse:
    checklist = await session.get(Checklist, checklist_id)
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "checklist_not_found", "message": "Checklist not found"})

    tasks = list(
        (
            await session.scalars(
                select(Task)
                .options(selectinload(Task.backlog_link))
                .where(Task.checklist_id == checklist_id, Task.id.in_(request.task_ids))
            )
        ).all()
    )
    if len(tasks) != len(request.task_ids):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "invalid_input", "message": "Tasks must belong to the checklist"})
    if any(task.backlog_link is not None for task in tasks):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "task_already_issued", "message": "Selected tasks already include an issued task"})

    available_business_days = business_day_count(request.start_date, request.end_date)
    total_capacity_hours = available_business_days * request.expected_assignee_count * 8
    if (
        available_business_days == 0
        or sum(task.estimated_hours for task in tasks) > total_capacity_hours
        or any(ceil(task.estimated_hours / 8) > available_business_days for task in tasks)
    ):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "schedule_impossible", "message": "The requested period and assignee count cannot accommodate the tasks"})

    try:
        generated_items = await schedule_generator.generate_schedule(
            checklist_name=checklist.name,
            tasks=[
                {"task_id": task.id, "title": task.title, "summary": task.summary, "estimated_hours": task.estimated_hours}
                for task in tasks
            ],
            start_date=request.start_date.isoformat(),
            end_date=request.end_date.isoformat(),
            expected_assignee_count=request.expected_assignee_count,
        )
        validate_schedule(generated_items, tasks, request)
    except GeminiConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "integration_not_configured", "message": "Gemini integration is not configured"}) from error
    except GeminiRequestError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={"code": "gemini_request_failed", "message": "Gemini request failed"}) from error
    except GeminiResponseError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={"code": "invalid_ai_schedule", "message": "Gemini returned an invalid schedule"}) from error

    plan = BacklogPlan(
        checklist_id=checklist.id,
        backlog_project_key_or_url=checklist.backlog_project_key_or_url,
        start_date=request.start_date,
        end_date=request.end_date,
        expected_assignee_count=request.expected_assignee_count,
    )
    session.add(plan)
    await session.flush()
    task_by_id = {task.id: task for task in tasks}
    items = [
        BacklogPlanItem(
            backlog_plan_id=plan.id,
            task_id=generated.task_id,
            title=task_by_id[generated.task_id].title,
            summary=task_by_id[generated.task_id].summary,
            estimated_hours=task_by_id[generated.task_id].estimated_hours,
            assignee_slot=generated.assignee_slot,
            start_date=generated.start_date,
            due_date=generated.due_date,
            depends_on_task_ids=generated.depends_on_task_ids,
        )
        for generated in generated_items
    ]
    session.add_all(items)
    await session.commit()
    return BacklogPlanCreateResponse(
        plan_id=plan.id,
        checklist_id=checklist.id,
        status="planned",
        start_date=plan.start_date,
        end_date=plan.end_date,
        expected_assignee_count=plan.expected_assignee_count,
        items=[
            BacklogPlanItemResponse(
                task_id=item.task_id,
                title=item.title,
                estimated_hours=item.estimated_hours,
                assignee_slot=item.assignee_slot,
                start_date=item.start_date,
                due_date=item.due_date,
                depends_on_task_ids=item.depends_on_task_ids,
            )
            for item in items
        ],
    )


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
