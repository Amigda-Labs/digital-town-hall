from dotenv import load_dotenv
load_dotenv()

import os
import asyncio
from agents import Runner, trace
from core.context import TownHallContext
from core.database import init_db, DATABASE_URL
from agents.extensions.memory import SQLAlchemySession

# Import from package (not submodule) to ensure __init__.py runs first
# See: docs/circular-imports.md#package-import-vs-submodule-import
from town_hall_agents import dialogue_agent

from openai.types.responses import ResponseTextDeltaEvent
import uuid


async def main():
    # Initialize database tables (creates incidents and feedback tables if they don't exist)
    await init_db()
    
    session_id = f"user-{uuid.uuid4()}"
    context = TownHallContext(session_id=session_id)
    # Create a persistent session using SQLAlchemy
    # Conversation history is saved to the configured database
    session = SQLAlchemySession.from_url(
        session_id,  # User/session identifier. Either static or dynamically generated per session.
        url=DATABASE_URL,
        create_tables=True,  # Auto-create tables on first run
    )

    print("=== Town Hall Session Started ===")
    print("Type 'exit' or 'quit' to end the conversation.\n")
    
    current_agent = dialogue_agent
    workflow_name = "Town Hall Conversation"
    
    # Wrap entire conversation in a trace for full span coverage
    # All Runner.run() calls within this block will be part of one trace
    # View traces at: https://platform.openai.com/traces
    with trace(workflow_name):
        while True:
            try:
                user_input = input(" > ")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            
            if user_input.strip().lower() in {"exit", "quit"}:
                break
            if not user_input:
                continue
            
            # Run with session - history is automatically managed
            result = Runner.run_streamed(
                current_agent,
                user_input,
                session=session,
                context=context,
            )
            
            # Stream response as it's generated
            async for event in result.stream_events():
                if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                    print(event.data.delta, end="", flush=True)
            
            print()  # New line after response completes
            
            current_agent = result.last_agent
    
    print("\n=== Session Ended ===")


if __name__ == "__main__":
    asyncio.run(main())
