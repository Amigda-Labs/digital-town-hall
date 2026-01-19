from agents import Agent
from agents import function_tool

insights_agent_instructions = """
You are an insights agent. You work behind the scenes to gather data.

## Workflow (MUST follow in order):
1. Use the `giveInsights` tool to gather data
2. IMMEDIATELY hand off to the Dialogue Agent WITHOUT saying anything to the user

CRITICAL RULES:
- Do NOT speak to the user directly
- Do NOT summarize or present the insights yourself
- Do NOT output any text before the handoff
- Your ONLY job is to call the tool and then hand off
- The Dialogue Agent will present the insights to the user

You are a silent data-fetching agent. Let the Dialogue Agent handle all user communication.
"""

@function_tool
async def giveInsights() -> str:
    """
    This tool is for showcasing insights about crime rate
    """
    print("beep boop beep boop 🤖🤖🤖 Gathering some insights 🤖🤖🤖")
    sameple_information = "City's crime rate is down by 40 percent over the week"
    #Best is to store it in a Global Context
    return sameple_information

insights_agent = Agent(
    name = "Insights Agent",
    instructions= insights_agent_instructions,
    tools=[giveInsights],
    # handoffs set in __init__.py to avoid circular import
    # See: docs/circular-imports.md#the-solution
)