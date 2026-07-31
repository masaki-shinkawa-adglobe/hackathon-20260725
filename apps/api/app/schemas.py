from datetime import date, datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TaskPriority = Literal["low", "medium", "high"]
BacklogRegistrationStatus = Literal["unregistered", "partial", "registered"]


class ChecklistWriteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    backlog_project_key_or_url: str | None = None

    @field_validator("name")
    @classmethod
    def reject_blank_name(cls, value: str) -> str:
        normalized_value = value.strip()
        if normalized_value == "":
            raise ValueError("Name must not be blank")
        return normalized_value


class ChecklistCreateRequest(ChecklistWriteRequest):
    pass


class ChecklistUpdateRequest(ChecklistWriteRequest):
    assignee_count: int = Field(default=None, ge=1, strict=True)

    @field_validator("description")
    @classmethod
    def normalize_blank_description(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            return None
        return value


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


class BacklogPlanCreateRequest(BaseModel):
    task_ids: list[int] = Field(min_length=1)
    start_date: date
    end_date: date
    expected_assignee_count: int = Field(ge=1, strict=True)

    @field_validator("task_ids")
    @classmethod
    def reject_duplicate_task_ids(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("task_ids must not contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_date_range(self) -> "BacklogPlanCreateRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self


class GeneratedScheduleItem(BaseModel):
    task_id: int
    assignee_slot: int
    start_date: date
    due_date: date
    depends_on_task_ids: list[int] = Field(default_factory=list)


class BacklogPlanItemResponse(BaseModel):
    task_id: int
    title: str
    estimated_hours: float
    assignee_slot: int
    start_date: date
    due_date: date
    depends_on_task_ids: list[int]


class BacklogPlanCreateResponse(BaseModel):
    plan_id: int
    checklist_id: int
    status: Literal["planned"]
    start_date: date
    end_date: date
    expected_assignee_count: int
    items: list[BacklogPlanItemResponse]


class ManualTaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    summary: str | None = None
    estimated_hours: float = Field(gt=0, allow_inf_nan=False)

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("summary", mode="before")
    @classmethod
    def normalize_blank_summary(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


class TaskUpdateRequest(ManualTaskCreateRequest):
    priority: TaskPriority


class ChecklistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    checklist_id: int
    title: str
    summary: str | None
    estimated_hours: float
    priority: TaskPriority


class TaskDetailResponse(BaseModel):
    checklist_name: str
    task: TaskResponse


class AIBulkTasksResponse(BaseModel):
    checklist: ChecklistResponse
    tasks: list[TaskResponse]


class BacklogRegistrationResponse(BaseModel):
    status: BacklogRegistrationStatus
    issued_task_count: int
    total_task_count: int
    last_issued_at: datetime | None


class ChecklistListItemResponse(BaseModel):
    id: int
    name: str
    task_count: int
    assignee_count: int
    backlog_registration: BacklogRegistrationResponse
    updated_at: datetime


class ChecklistsResponse(BaseModel):
    checklists: list[ChecklistListItemResponse]


class ChecklistDetailResponse(ChecklistResponse):
    assignee_count: int
    backlog_registration: BacklogRegistrationResponse
    tasks: list[TaskResponse]
