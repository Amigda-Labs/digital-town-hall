from agents import Agent

insights_agent_instructions = "You are an insights agent. Your goal is to give insights regarding the user's question."

insights_agent = Agent(
    name = "Insights Agent",
    instructions= insights_agent_instructions
)