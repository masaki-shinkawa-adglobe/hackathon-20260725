from pydantic import BaseModel, ConfigDict, Field


class AIBulkTasksRequest(BaseModel):
    checklist_id: int
    description: str | None = Field(default=None, max_length=10_000)


class GeneratedTask(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1)
    estimated_hours: float = Field(gt=0, allow_inf_nan=False)


class ChecklistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class TaskResponse(GeneratedTask):
    model_config = ConfigDict(from_attributes=True)

    id: int
    checklist_id: int


class AIBulkTasksResponse(BaseModel):
    checklist: ChecklistResponse
    tasks: list[TaskResponse]
