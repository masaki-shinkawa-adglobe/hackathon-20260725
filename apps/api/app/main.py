from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine, get_session
from app.gemini import (
    GeminiConfigurationError,
    GeminiRequestError,
    GeminiResponseError,
    TaskGenerator,
    get_task_generator,
)
from app.models import Checklist, Task
from app.schemas import AIBulkTasksRequest, AIBulkTasksResponse


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


@app.post("/checklists/ai-bulk-tasks", response_model=AIBulkTasksResponse)
async def create_ai_bulk_tasks(
    request: AIBulkTasksRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    task_generator: Annotated[TaskGenerator, Depends(get_task_generator)],
) -> AIBulkTasksResponse:
    checklist = await session.scalar(
        select(Checklist).where(Checklist.id == request.checklist_id)
    )
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist not found")

    try:
        generated_tasks = await task_generator.generate_tasks(
            checklist_name=checklist.name, description=request.description
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
