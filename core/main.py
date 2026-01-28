from dotenv import load_dotenv
load_dotenv()

import asyncio
from agents import Runner, SQLiteSession, trace
from core.context import TownHallContext
import uuid


# Import from package (not submodule) to ensure __init__.py runs first
# See: docs/circular-imports.md#package-import-vs-submodule-import
from town_hall_agents import dialogue_agent


async def main():
    context = TownHallContext()
    
    # Create a persistent session - conversation history saved to conversations.db
    session_id = f"town_hall_{uuid.uuid4().hex[:8]}"
    session = SQLiteSession(session_id, "conversations.db")

    print("=== Town Hall Session Started ===")
    print(f"Session ID: {session_id}")
    print("Type 'exit' or 'quit' to end the conversation.\n")
    
    current_agent = dialogue_agent
    workflow_name = "Town Hall Conversation"
    
    # Wrap entire conversation in a trace for full span coverage
    # All Runner.run() calls within this block will be part of one trace
    # View traces at: https://platform.openai.com/traces
    with trace(workflow_name, group_id=session_id):
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
            result = await Runner.run(
                current_agent,
                user_input,
                session=session,
                context=context,
            )
            
            if result.final_output is not None:
                print(result.final_output)
            
            # Support agent handoffs
            current_agent = result.last_agent
    
    print("\n=== Session Ended ===")


if __name__ == "__main__":
    asyncio.run(main())
