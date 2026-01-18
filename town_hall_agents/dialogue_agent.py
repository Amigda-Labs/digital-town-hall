import os
from agents import Agent
from town_hall_agents.triage_agent import triage_agent
from agents import FileSearchTool

dialogue_agent_instructions = """
You are Dialogue Agent. You will be the agent directly conversing with the user.
Handover the user's message to the Triage Agent.
"""

file_search = FileSearchTool(
   max_num_results=3,
   vector_store_ids=[os.getenv("VECTOR_STORE_ID")]
)

dialogue_agent=Agent(
   name="Dialogue Agent",
   instructions=dialogue_agent_instructions,
   handoffs=[triage_agent],
   tools=[file_search]
)