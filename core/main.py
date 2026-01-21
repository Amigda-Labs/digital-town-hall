from dotenv import load_dotenv

from core.context import TownHallContext
load_dotenv()

import asyncio
from agents import run_demo_loop

# Import from package (not submodule) to ensure __init__.py runs first
# See: docs/circular-imports.md#package-import-vs-submodule-import
from town_hall_agents import dialogue_agent

async def main():
    context = TownHallContext()

    await run_demo_loop(
        dialogue_agent,
        context=context,
        )

if __name__ == "__main__":
    asyncio.run(main())
