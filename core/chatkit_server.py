"""
ChatKit server for Digital Town Hall.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from chatkit.server import ChatKitServer
from chatkit.types import (
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageItem,
)
import asyncio

from agents import Agent, Runner
from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response

from town_hall_agents import dialogue_agent
from core.context import TownHallContext
from core.database import save_incident, save_feedback

logger = logging.getLogger(__name__)



class TownHallChatKitServer(ChatKitServer[dict[str, Any]]):
    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        
        items_page = await self.store.load_thread_items(
            thread.id,
            after=None,
            limit=20,
            order="asc",
            context=context,
        )

        input_items = await simple_to_agent_input(items_page.data)

        town_hall_context = TownHallContext(session_id=thread.id)

        logger.info("agent_run_start thread=%s items=%d", thread.id, len(input_items))

        updating_thread_title = asyncio.create_task(
            self._maybe_update_thread_title(thread, context)
        )

        agent_context = AgentContext(thread=thread, store=self.store, request_context=context)
        result = Runner.run_streamed(
            dialogue_agent,
            input_items,
            context=town_hall_context,
        )

        async for event in stream_agent_response(agent_context, result):
            yield event

        logger.info("agent_run_end thread=%s stage=%s", thread.id, town_hall_context.agent_stage.value if town_hall_context.agent_stage else "none")

        # Await here so the ThreadUpdatedEvent is emitted before the response closes
        await updating_thread_title

        # Persist structured outputs to DB now that the agent run is complete.
        # Done here (not inside the function tools) so that:
        #  - thread.id is always available directly
        #  - any DB exception surfaces as a real server error instead of being
        #    silently swallowed by the agents SDK tool-error handler
        await self._persist_structured_outputs(town_hall_context, thread.id)

    async def _maybe_update_thread_title(self, thread: ThreadMetadata, context: dict) -> None:
        if thread.title is not None:
            return  # Already titled, skip

        items = await self.store.load_thread_items(
            thread.id, after=None, limit=6, order="desc", context=context
        )

        thread.title = await self._generate_short_title(items.data)
        await self.store.save_thread(thread, context=context)
        logger.info("thread_title_generated thread=%s title=%s", thread.id, thread.title)


    async def _generate_short_title(self, items) -> str:
        # Use a cheap model call — gpt-4.1-mini or even gpt-4o-mini works well here
        result = await Runner.run(
            Agent(
                name="title-generator",
                instructions="Generate a concise 3-6 word title summarizing this conversation. Reply with ONLY the title, no punctuation.",
                model="gpt-4.1-mini",
            ),
            input=str([item for item in items]),
        )
        return result.final_output.strip()

    async def _persist_structured_outputs(
        self, ctx: TownHallContext, session_id: str
    ) -> None:
        if ctx.incident_processed and ctx.incident is not None:
            try:
                db_incident = await save_incident(ctx.incident, session_id=session_id)
                logger.info("[persist] Incident saved to DB id=%s session=%s", db_incident.id, session_id)
            except Exception:
                logger.exception("[persist] Failed to save incident for session=%s", session_id)

        if ctx.feedback_processed and ctx.feedback is not None:
            try:
                db_feedback = await save_feedback(ctx.feedback, session_id=session_id)
                logger.info("[persist] Feedback saved to DB id=%s session=%s", db_feedback.id, session_id)
            except Exception:
                logger.exception("[persist] Failed to save feedback for session=%s", session_id)