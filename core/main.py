from dotenv import load_dotenv
load_dotenv()

import asyncio
from agents import run_demo_loop

from town_hall_agents.dialogue_agent import dialogue_agent

async def main():
    await run_demo_loop(dialogue_agent)

if __name__ == "__main__":
    asyncio.run(main())
