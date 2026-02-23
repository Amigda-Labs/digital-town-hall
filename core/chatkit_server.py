"""
ChatKit server for Digital Town Hall.
Hardcoded "Hello, world!" response for testing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, AsyncIterator

from chatkit.server import ChatKitServer
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageItem,
    ThreadItemDoneEvent,
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageItem,
)


class TownHallChatKitServer(ChatKitServer[dict[str, Any]]):
    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:

        yield ThreadItemDoneEvent(
            item=AssistantMessageItem(
                thread_id=thread.id,
                id=self.store.generate_item_id("message",thread, context),
                created_at=datetime.now(timezone.utc),
                content=[AssistantMessageContent(text="Hello, world!")],
            ),
        )