from datetime import UTC, datetime
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from app.checklists import checklist_items, checklists
from app.main import checklist_list_query, list_checklists

API_ROOT = Path(__file__).resolve().parents[1]


def to_asyncpg_url(url: str) -> str:
    return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")


def run_alembic(*arguments: str, database_url: str) -> None:
    environment = {**os.environ, "DATABASE_URL": database_url}
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=API_ROOT,
        env=environment,
        check=True,
    )


@pytest.mark.asyncio
async def test_list_checklists_aggregates_postgresql_data_after_migration() -> None:
    with PostgresContainer("postgres:18") as postgres:
        database_url = to_asyncpg_url(postgres.get_connection_url())
        run_alembic("upgrade", "head", database_url=database_url)
        run_alembic("check", database_url=database_url)

        engine = create_async_engine(database_url)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        empty_updated_at = datetime(2026, 7, 31, 11, 0, tzinfo=UTC)
        mixed_updated_at = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)

        try:
            async with engine.begin() as connection:
                await connection.execute(
                    insert(checklists),
                    [
                        {
                            "id": 1,
                            "name": "項目なし",
                            "description": None,
                            "updated_at": empty_updated_at,
                        },
                        {
                            "id": 2,
                            "name": "リリース準備",
                            "description": "本番公開前の確認",
                            "updated_at": mixed_updated_at,
                        },
                    ],
                )
                await connection.execute(
                    insert(checklist_items),
                    [
                        {
                            "checklist_id": 2,
                            "content": "承認を取得する",
                            "is_completed": True,
                            "position": 1,
                        },
                        {
                            "checklist_id": 2,
                            "content": "手順を確認する",
                            "is_completed": False,
                            "position": 2,
                        },
                    ],
                )

            async with session_factory() as session:
                response = await list_checklists(session)

            assert [item.model_dump() for item in response] == [
                {
                    "name": "リリース準備",
                    "description": "本番公開前の確認",
                    "completed_item_count": 1,
                    "total_item_count": 2,
                    "updated_at": mixed_updated_at,
                },
                {
                    "name": "項目なし",
                    "description": None,
                    "completed_item_count": 0,
                    "total_item_count": 0,
                    "updated_at": empty_updated_at,
                },
            ]
        finally:
            await engine.dispose()


def test_checklist_list_query_aggregates_in_one_database_query() -> None:
    compiled = str(checklist_list_query)

    assert "LEFT OUTER JOIN checklist_items" in compiled
    assert "GROUP BY checklists.id" in compiled
