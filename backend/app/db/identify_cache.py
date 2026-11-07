"""Final identify results keyed by video and 5-second bucket. Never fails a request."""

from __future__ import annotations

import logging

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.models import IdentifyCacheEntry
from app.schemas import Candidates

BUCKET_SECONDS = 5

logger = logging.getLogger(__name__)


def bucket_of(t: float) -> int:
    return int(t // BUCKET_SECONDS)


class IdentifyCache:
    def __init__(self, database_url: str | None) -> None:
        self._engine: AsyncEngine | None = None
        self._sessions: async_sessionmaker[AsyncSession] | None = None
        if database_url:
            # /lookup runs before every capture, so a missing database must fail in
            # seconds, not after asyncpg's 60 s default connect timeout.
            self._engine = create_async_engine(
                database_url, connect_args={"timeout": 2}
            )
            self._sessions = async_sessionmaker(self._engine, expire_on_commit=False)

    async def get(self, video_id: str, t: float) -> Candidates | None:
        if self._sessions is None:
            return None
        try:
            async with self._sessions() as session:
                entry = await session.get(IdentifyCacheEntry, (video_id, bucket_of(t)))
        except (SQLAlchemyError, OSError) as error:
            logger.warning(
                "Identify cache lookup failed, treating as a miss: %s", error
            )
            return None
        return Candidates.model_validate(entry.result) if entry else None

    async def put(self, video_id: str, t: float, result: Candidates) -> None:
        if self._sessions is None:
            return
        values = {
            "video_id": video_id,
            "bucket": bucket_of(t),
            "result": result.model_dump(mode="json"),
        }
        statement = insert(IdentifyCacheEntry).values(values)
        statement = statement.on_conflict_do_update(
            index_elements=["video_id", "bucket"],
            set_={
                "result": statement.excluded.result,
                "created_at": statement.excluded.created_at,
            },
        )
        try:
            async with self._sessions() as session, session.begin():
                await session.execute(statement)
        except (SQLAlchemyError, OSError) as error:
            logger.warning("Identify cache write skipped: %s", error)

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
