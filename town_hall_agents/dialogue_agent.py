from agents import Agent
from town_hall_agents.triage_agent import triage_agent

dialogue_agent_instructions = """
You are Dialogue Agent. You will be the agent directly conversing with the user.
Handover the user's message to the Triage Agent.
"""

dialogue_agent=Agent(
   name="Dialogue Agent",
   instructions=dialogue_agent_instructions,
   handoffs=[triage_agent]
)