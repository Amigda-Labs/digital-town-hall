from dotenv import load_dotenv
load_dotenv()

import asyncio
from agents import run_demo_loop

# Import from package (not submodule) to ensure __init__.py runs first
# See: docs/circular-imports.md#package-import-vs-submodule-import
from town_hall_agents import dialogue_agent

async def main():
    await run_demo_loop(dialogue_agent)

if __name__ == "__main__":
    asyncio.run(main())
