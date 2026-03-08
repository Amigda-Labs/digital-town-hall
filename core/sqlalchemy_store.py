"""
Database-backed ChatKit store using SQLAlchemy.

Replaces MemoryStore so threads and items survive server restarts.
Uses the same async engine / session factory configured in core.database.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy import select, delete, and_

from chatkit.store import NotFoundError, Store
from chatkit.types import Attachment, Page, ThreadItem, ThreadMetadata

from core.database import (
    AsyncSessionLocal,
    ChatKitThreadModel,
    ChatKitThreadItemModel,
)

_thread_item_ta = TypeAdapter(ThreadItem)


def _thread_from_row(row: ChatKitThreadModel) -> ThreadMetadata:
    status = json.loads(row.status_json)
    metadata = json.loads(row.metadata_json)
    return ThreadMetadata(
        id=row.id,
        title=row.title,
        created_at=row.created_at,
        status=status,
        metadata=metadata,
    )


def _item_from_row(row: ChatKitThreadItemModel) -> ThreadItem:
    return _thread_item_ta.validate_json(row.item_json)


class SQLAlchemyStore(Store[dict]):
    """ChatKit Store backed by SQLAlchemy (SQLite or PostgreSQL)."""

    # ---- threads -----------------------------------------------------------

    async def load_thread(self, thread_id: str, context: dict) -> ThreadMetadata:
        async with AsyncSessionLocal() as session:
            row = await session.get(ChatKitThreadModel, thread_id)
            if row is None:
                raise NotFoundError(f"Thread {thread_id} not found")
            return _thread_from_row(row)

    async def save_thread(self, thread: ThreadMetadata, context: dict) -> None:
        async with AsyncSessionLocal() as session:
            row = await session.get(ChatKitThreadModel, thread.id)
            if row is None:
                row = ChatKitThreadModel(
                    id=thread.id,
                    title=thread.title,
                    created_at=thread.created_at,
                    status_json=json.dumps(thread.status.model_dump()),
                    metadata_json=json.dumps(thread.metadata),
                    device_id=context.get("device_id"),
                )
                session.add(row)
            else:
                row.title = thread.title
                row.status_json = json.dumps(thread.status.model_dump())
                row.metadata_json = json.dumps(thread.metadata)
            await session.commit()

    async def load_threads(
        self, limit: int, after: str | None, order: str, context: dict
    ) -> Page[ThreadMetadata]:
        async with AsyncSessionLocal() as session:
            desc = order == "desc"
            col = ChatKitThreadModel.created_at
            id_col = ChatKitThreadModel.id
            ordering = (col.desc(), id_col.desc()) if desc else (col.asc(), id_col.asc())

            stmt = select(ChatKitThreadModel)

            device_id = context.get("device_id")
            if device_id:
                stmt = stmt.where(ChatKitThreadModel.device_id == device_id)

            if after:
                cursor_row = await session.get(ChatKitThreadModel, after)
                if cursor_row is not None:
                    if desc:
                        stmt = stmt.where(
                            (col < cursor_row.created_at)
                            | (and_(col == cursor_row.created_at, id_col < cursor_row.id))
                        )
                    else:
                        stmt = stmt.where(
                            (col > cursor_row.created_at)
                            | (and_(col == cursor_row.created_at, id_col > cursor_row.id))
                        )

            stmt = stmt.order_by(*ordering).limit(limit + 1)
            result = await session.execute(stmt)
            rows = list(result.scalars().all())

            has_more = len(rows) > limit
            rows = rows[:limit]
            data = [_thread_from_row(r) for r in rows]
            next_after = rows[-1].id if has_more and rows else None
            return Page(data=data, has_more=has_more, after=next_after)

    async def delete_thread(self, thread_id: str, context: dict) -> None:
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(ChatKitThreadItemModel).where(
                    ChatKitThreadItemModel.thread_id == thread_id
                )
            )
            await session.execute(
                delete(ChatKitThreadModel).where(ChatKitThreadModel.id == thread_id)
            )
            await session.commit()

    # ---- thread items ------------------------------------------------------

    async def load_thread_items(
        self, thread_id: str, after: str | None, limit: int, order: str, context: dict
    ) -> Page[ThreadItem]:
        async with AsyncSessionLocal() as session:
            desc = order == "desc"
            col = ChatKitThreadItemModel.created_at
            id_col = ChatKitThreadItemModel.id
            ordering = (col.desc(), id_col.desc()) if desc else (col.asc(), id_col.asc())

            stmt = select(ChatKitThreadItemModel).where(
                ChatKitThreadItemModel.thread_id == thread_id
            )

            if after:
                cursor_row = await session.get(ChatKitThreadItemModel, after)
                if cursor_row is not None:
                    if desc:
                        stmt = stmt.where(
                            (col < cursor_row.created_at)
                            | (and_(col == cursor_row.created_at, id_col < cursor_row.id))
                        )
                    else:
                        stmt = stmt.where(
                            (col > cursor_row.created_at)
                            | (and_(col == cursor_row.created_at, id_col > cursor_row.id))
                        )

            stmt = stmt.order_by(*ordering).limit(limit + 1)
            result = await session.execute(stmt)
            rows = list(result.scalars().all())

            has_more = len(rows) > limit
            rows = rows[:limit]
            data = [_item_from_row(r) for r in rows]
            next_after = rows[-1].id if has_more and rows else None
            return Page(data=data, has_more=has_more, after=next_after)

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: dict
    ) -> None:
        async with AsyncSessionLocal() as session:
            row = ChatKitThreadItemModel(
                id=item.id,
                thread_id=thread_id,
                item_type=item.type,
                created_at=item.created_at,
                item_json=item.model_dump_json(),
            )
            session.add(row)
            await session.commit()

    async def save_item(
        self, thread_id: str, item: ThreadItem, context: dict
    ) -> None:
        async with AsyncSessionLocal() as session:
            row = await session.get(ChatKitThreadItemModel, item.id)
            if row is None:
                row = ChatKitThreadItemModel(
                    id=item.id,
                    thread_id=thread_id,
                    item_type=item.type,
                    created_at=item.created_at,
                    item_json=item.model_dump_json(),
                )
                session.add(row)
            else:
                row.item_json = item.model_dump_json()
                row.item_type = item.type
            await session.commit()

    async def load_item(
        self, thread_id: str, item_id: str, context: dict
    ) -> ThreadItem:
        async with AsyncSessionLocal() as session:
            row = await session.get(ChatKitThreadItemModel, item_id)
            if row is None or row.thread_id != thread_id:
                raise NotFoundError(f"Item {item_id} not found in thread {thread_id}")
            return _item_from_row(row)

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: dict
    ) -> None:
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(ChatKitThreadItemModel).where(
                    ChatKitThreadItemModel.id == item_id,
                    ChatKitThreadItemModel.thread_id == thread_id,
                )
            )
            await session.commit()

    # ---- attachments (not implemented) -------------------------------------

    async def save_attachment(self, attachment: Attachment, context: dict) -> None:
        raise NotImplementedError()

    async def load_attachment(self, attachment_id: str, context: dict) -> Attachment:
        raise NotImplementedError()

    async def delete_attachment(self, attachment_id: str, context: dict) -> None:
        raise NotImplementedError()
