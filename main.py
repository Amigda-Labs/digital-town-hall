from agents import Agent

from dotenv import load_dotenv
load_dotenv()

import asyncio
from agents import run_demo_loop


dialogue_agent=Agent(
   name="Dialogue Agent",
   instructions="You are Dialogue Agent. You will be the agent directly conversing with the user."
)

async def main():
    await run_demo_loop(dialogue_agent)

if __name__ == "__main__":
    asyncio.run(main())
