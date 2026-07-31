import asyncio
import json
import os
from typing import Protocol

from pydantic import TypeAdapter, ValidationError

from app.schemas import GeneratedTask


class GeminiConfigurationError(Exception):
    pass


class GeminiRequestError(Exception):
    pass


class GeminiResponseError(Exception):
    pass


class TaskGenerator(Protocol):
    async def generate_tasks(
        self, *, checklist_name: str, description: str | None
    ) -> list[GeneratedTask]: ...


class GeminiTaskGenerator:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def generate_tasks(
        self, *, checklist_name: str, description: str | None
    ) -> list[GeneratedTask]:
        prompt = (
            "次のチェックリストを実行可能な複数タスクへ分解してください。"
            "JSON配列だけを返してください。各要素は title, summary, estimated_hours "
            "（時間、正の数値）を必須とします。\n"
            f"チェックリスト名: {checklist_name}\n"
            f"補足説明: {description or 'なし'}"
        )
        try:
            response_text = await asyncio.to_thread(self._request, prompt)
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

    def _request(self, prompt: str) -> str:
        try:
            from google import genai
            from google.genai import types
        except ImportError as error:
            raise GeminiConfigurationError("Gemini SDK is not installed") from error

        client = genai.Client(api_key=self._api_key)
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        if not response.text:
            raise GeminiResponseError("Gemini returned an empty response")
        return response.text


class EnvironmentGeminiTaskGenerator:
    async def generate_tasks(
        self, *, checklist_name: str, description: str | None
    ) -> list[GeneratedTask]:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise GeminiConfigurationError("GEMINI_API_KEY is not configured")
        return await GeminiTaskGenerator(api_key).generate_tasks(
            checklist_name=checklist_name, description=description
        )


def get_task_generator() -> TaskGenerator:
    return EnvironmentGeminiTaskGenerator()
