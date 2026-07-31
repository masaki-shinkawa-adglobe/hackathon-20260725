"""Local-development and pilot-data seeder.

This module intentionally does not call Gemini or any other external service.
"""

import asyncio
from collections.abc import Sequence

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import async_session_factory
from app.models import Checklist, Task


class PriorityDependencyError(RuntimeError):
    """Raised when the priority support from Issue #120 is not available."""


SEED_CHECKLISTS: tuple[dict[str, object], ...] = (
    {
        "name": "パイロット: 月次運用",
        "description": "パイロット環境で月次運用を確認するためのサンプルです。",
        "tasks": (
            ("対象期間を確認", "対象となる月と締め日を確認する。", 0.5, "high"),
            ("必要資料を収集", "請求書、明細、証憑を収集する。", 2.0, "medium"),
            ("取引を照合", "主要な入出金と帳票を照合する。", 2.0, "high"),
            ("差異を記録", "差異と対応方針を記録する。", 1.0, "low"),
            ("担当者へ確認", "未解決の差異を担当者へ確認する。", 1.0, None),
            ("完了報告を作成", "月次作業の結果を関係者へ共有する。", 0.5, "medium"),
            ("次月の改善点を整理", "次回に向けた改善点を整理する。", 0.5, "low"),
        ),
    },
    {
        "name": "パイロット: リリース準備",
        "description": "パイロット環境でリリース準備の流れを確認するためのサンプルです。",
        "tasks": (
            ("リリース内容を確定", "対象機能と変更点を確定する。", 1.0, "high"),
            ("手順書を更新", "運用手順書を最新化する。", 1.5, "medium"),
            ("テスト結果を確認", "受入テストの結果を確認する。", 1.0, "high"),
            ("関係者へ連絡", "リリース日時と影響を周知する。", 0.5, None),
            ("ロールバック手順を確認", "切戻し条件と手順を確認する。", 1.0, "high"),
            ("監視項目を確認", "リリース後に確認する監視項目を整理する。", 0.5, "low"),
            ("完了連絡を送付", "リリース完了を関係者へ連絡する。", 0.5, "medium"),
        ),
    },
    {
        "name": "パイロット: 新規メンバー受入",
        "description": "パイロット環境で新規メンバー受入の進め方を確認するためのサンプルです。",
        "tasks": (
            ("受入日を調整", "初日の予定を関係者と調整する。", 0.5, "medium"),
            ("アカウントを準備", "必要なアカウントと権限を準備する。", 1.0, "high"),
            ("端末を準備", "利用端末と周辺機器を準備する。", 1.0, "medium"),
            ("オリエンテーションを実施", "チームの目的と基本ルールを説明する。", 1.5, None),
            ("初回タスクを割り当て", "小さな初回タスクを割り当てる。", 0.5, "high"),
            ("振り返りを実施", "初週の困りごとと改善点を確認する。", 0.5, "low"),
        ),
    },
)


def _require_priority_support() -> None:
    mapper = inspect(Task)
    if "priority" not in Task.__table__.c or "priority" not in mapper.attrs:
        raise PriorityDependencyError(
            "Task priority is unavailable. Apply Issue #120 (priority column, ORM, and API schema) "
            "and run its migration before running this seeder."
        )


async def seed(session_factory: async_sessionmaker[AsyncSession] = async_session_factory) -> bool:
    """Insert fixed pilot data once.  Return False when it already exists."""
    _require_priority_support()
    names = [str(checklist["name"]) for checklist in SEED_CHECKLISTS]

    async with session_factory() as session:
        existing = await session.scalar(select(Checklist.id).where(Checklist.name.in_(names)).limit(1))
        if existing is not None:
            print("Seed data already exists; no records were created or deleted.")
            return False

        checklists: list[Checklist] = []
        for seed_checklist in SEED_CHECKLISTS:
            checklist = Checklist(
                name=str(seed_checklist["name"]),
                description=str(seed_checklist["description"]),
            )
            session.add(checklist)
            checklists.append(checklist)
        await session.flush()

        for checklist, seed_checklist in zip(checklists, SEED_CHECKLISTS, strict=True):
            tasks: Sequence[tuple[str, str, float, str | None]] = seed_checklist["tasks"]  # type: ignore[assignment]
            for title, summary, estimated_hours, priority in tasks:
                values: dict[str, object] = {
                    "checklist_id": checklist.id,
                    "title": title,
                    "summary": summary,
                    "estimated_hours": estimated_hours,
                }
                if priority is not None:
                    values["priority"] = priority
                session.add(Task(**values))

        await session.commit()

    print(f"Created {len(checklists)} checklists and {sum(len(item['tasks']) for item in SEED_CHECKLISTS)} tasks.")
    return True


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
