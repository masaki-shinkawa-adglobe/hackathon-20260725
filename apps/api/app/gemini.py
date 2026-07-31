import asyncio
import json
import os
from dataclasses import dataclass
from typing import Protocol

from pydantic import TypeAdapter, ValidationError

from app.schemas import GeneratedScheduleItem, GeneratedTask


class GeminiConfigurationError(Exception):
    pass


class GeminiRequestError(Exception):
    pass


class GeminiResponseError(Exception):
    pass


@dataclass(frozen=True)
class TaskSource:
    text: str | None = None
    document: bytes | None = None
    document_mime_type: str | None = None


class TaskGenerator(Protocol):
    async def generate_tasks(
        self, *, checklist_name: str, description: str | None = None, source: TaskSource | None = None
    ) -> list[GeneratedTask]: ...


class ScheduleGenerator(Protocol):
    async def generate_schedule(
        self,
        *,
        checklist_name: str,
        tasks: list[dict[str, object]],
        start_date: str,
        end_date: str,
        expected_assignee_count: int,
    ) -> list[GeneratedScheduleItem]: ...


class GeminiTaskGenerator:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def generate_tasks(
        self, *, checklist_name: str, description: str | None = None, source: TaskSource | None = None
    ) -> list[GeneratedTask]:
        prompt = (
            "次のチェックリストを実行可能な複数タスクへ分解してください。"
            "JSON配列だけを返してください。各要素は title, summary, estimated_hours "
            "（時間、正の数値）を必須とします。\n"
            f"チェックリスト名: {checklist_name}\n"
            f"補足説明: {description or 'なし'}\n"
            f"添付ファイルから抽出した内容: {source.text if source and source.text else 'なし'}"
        )
        try:
            response_text = await asyncio.to_thread(self._request, prompt, source)
        except (GeminiConfigurationError, GeminiResponseError):
            raise
        except Exception as error:
            raise GeminiRequestError("Gemini API request failed") from error

        try:
            payload = json.loads(response_text)
            tasks = TypeAdapter(list[GeneratedTask]).validate_python(payload)
        except (json.JSONDecodeError, ValidationError, TypeError) as error:
            raise GeminiResponseError("Gemini returned an invalid task list") from error
        if not tasks:
            raise GeminiResponseError("Gemini returned an empty task list")
        return tasks

    def _request(self, prompt: str, source: TaskSource | None = None) -> str:
        try:
            from google import genai
            from google.genai import types
        except ImportError as error:
            raise GeminiConfigurationError("Gemini SDK is not installed") from error

        client = genai.Client(api_key=self._api_key)
        contents: str | list[object] = prompt
        if source and source.document:
            contents = [
                prompt,
                types.Part.from_bytes(data=source.document, mime_type=source.document_mime_type or "application/pdf"),
            ]
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
            contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        if not response.text:
            raise GeminiResponseError("Gemini returned an empty response")
        return response.text


class EnvironmentGeminiTaskGenerator:
    async def generate_tasks(
        self, *, checklist_name: str, description: str | None = None, source: TaskSource | None = None
    ) -> list[GeneratedTask]:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise GeminiConfigurationError("GEMINI_API_KEY is not configured")
        return await GeminiTaskGenerator(api_key).generate_tasks(
            checklist_name=checklist_name, description=description, source=source
        )


def get_task_generator() -> TaskGenerator:
    return EnvironmentGeminiTaskGenerator()


class GeminiScheduleGenerator:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def generate_schedule(
        self,
        *,
        checklist_name: str,
        tasks: list[dict[str, object]],
        start_date: str,
        end_date: str,
        expected_assignee_count: int,
    ) -> list[GeneratedScheduleItem]:
        prompt = (
            "次の既存タスクの日程計画を作成してください。JSON配列だけを返してください。"
            "各要素は task_id, assignee_slot, start_date, due_date, depends_on_task_ids を必須とします。"
            "タスクを追加、削除、分割、統合せず、与えられたtask_idを各1回だけ返してください。"
            "担当枠は1から指定数までです。1人1日8時間、土日非稼働、祝日無視です。"
            "各タスクは1枠を連続占有し、所要営業日数はceil(estimated_hours / 8)です。"
            "依存先の期限日の次の営業日以降に後続タスクを開始してください。\n"
            f"チェックリスト名: {checklist_name}\n"
            f"開始日: {start_date}\n期限日: {end_date}\n担当枠数: {expected_assignee_count}\n"
            f"タスク: {json.dumps(tasks, ensure_ascii=False)}"
        )
        try:
            response_text = await asyncio.to_thread(self._request, prompt)
        except (GeminiConfigurationError, GeminiResponseError):
            raise
        except Exception as error:
            raise GeminiRequestError("Gemini API request failed") from error
        try:
            schedule = TypeAdapter(list[GeneratedScheduleItem]).validate_python(json.loads(response_text))
        except (json.JSONDecodeError, ValidationError, TypeError) as error:
            raise GeminiResponseError("Gemini returned an invalid schedule") from error
        if not schedule:
            raise GeminiResponseError("Gemini returned an empty schedule")
        return schedule

    def _request(self, prompt: str) -> str:
        return GeminiTaskGenerator(self._api_key)._request(prompt)


class EnvironmentGeminiScheduleGenerator:
    async def generate_schedule(self, **kwargs: object) -> list[GeneratedScheduleItem]:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise GeminiConfigurationError("GEMINI_API_KEY is not configured")
        return await GeminiScheduleGenerator(api_key).generate_schedule(**kwargs)  # type: ignore[arg-type]


def get_schedule_generator() -> ScheduleGenerator:
    return EnvironmentGeminiScheduleGenerator()
