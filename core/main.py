from dotenv import load_dotenv
load_dotenv()

import asyncio
from agents import Runner, trace
from core.context import TownHallContext
from agents import OpenAIConversationsSession

# Import from package (not submodule) to ensure __init__.py runs first
# See: docs/circular-imports.md#package-import-vs-submodule-import
from town_hall_agents import dialogue_agent

from openai.types.responses import ResponseTextDeltaEvent


async def main():
    context = TownHallContext()
    
    # Create a persistent session - conversation history saved to conversations.db
    session = OpenAIConversationsSession()

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
