from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChecklistWriteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    backlog_project_key_or_url: str | None = None

    @field_validator("name")
    @classmethod
    def reject_blank_name(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("Name must not be blank")
        return value


class ChecklistCreateRequest(ChecklistWriteRequest):
    pass


class ChecklistUpdateRequest(ChecklistWriteRequest):
    assignee_count: int = Field(ge=1, strict=True)


class ChecklistCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    backlog_project_key_or_url: str | None


class ChecklistUpdateResponse(ChecklistCreateResponse):
    assignee_count: int


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
    assignee_count: int
    backlog_last_registered_at: datetime | None
    updated_at: datetime


class ChecklistsResponse(BaseModel):
    checklists: list[ChecklistListItemResponse]


class ChecklistDetailResponse(ChecklistResponse):
    assignee_count: int
    backlog_registration: BacklogRegistrationResponse
    tasks: list[TaskResponse]
