from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AIBulkTasksUploadRequest(BaseModel):
    checklist_id: int
    description: str | None = Field(default=None, max_length=10_000)

    @field_validator("description")
    @classmethod
    def normalize_blank_description(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            return None
        return value


class GeneratedTask(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1)
    estimated_hours: float = Field(gt=0, allow_inf_nan=False)


class ChecklistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None


class TaskResponse(GeneratedTask):
    model_config = ConfigDict(from_attributes=True)

    id: int
    checklist_id: int


class AIBulkTasksResponse(BaseModel):
    checklist: ChecklistResponse
    tasks: list[TaskResponse]


class BacklogRegistrationResponse(BaseModel):
    is_registered: bool
    link_id: int | None
    backlog_issue_id: int | None
    backlog_issue_key: str | None
    backlog_issue_url: str | None


class ChecklistListItemResponse(BaseModel):
    id: int
    name: str
    task_count: int
    backlog_registration: BacklogRegistrationResponse
    updated_at: datetime


class ChecklistsResponse(BaseModel):
    checklists: list[ChecklistListItemResponse]


class ChecklistDetailResponse(ChecklistResponse):
    backlog_registration: BacklogRegistrationResponse
    tasks: list[TaskResponse]
