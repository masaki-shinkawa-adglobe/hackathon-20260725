from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from datetime import datetime

from fastapi import Depends, FastAPI
from pydantic import BaseModel
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.checklists import checklist_items, checklists
from app.database import engine, get_session


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)


class ChecklistListItem(BaseModel):
    name: str
    description: str | None
    completed_item_count: int
    total_item_count: int
    updated_at: datetime


checklist_list_query = (
    select(
        checklists.c.name,
        checklists.c.description,
        func.coalesce(
            func.sum(case((checklist_items.c.is_completed.is_(True), 1), else_=0)), 0
        ).label("completed_item_count"),
        func.count(checklist_items.c.id).label("total_item_count"),
        checklists.c.updated_at,
    )
    .select_from(checklists.outerjoin(checklist_items))
    .group_by(checklists.c.id)
    .order_by(checklists.c.updated_at.desc())
)


@app.get("/health")
async def health(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/checklists", response_model=list[ChecklistListItem])
async def list_checklists(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ChecklistListItem]:
    result = await session.execute(checklist_list_query)
    return [ChecklistListItem.model_validate(row) for row in result.mappings()]
