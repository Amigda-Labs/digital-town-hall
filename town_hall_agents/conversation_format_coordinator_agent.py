from agents import Agent
from pydantic import BaseModel


from town_hall_agents.feedback_formatter_agent import feedback_formatter_tool
from town_hall_agents.incident_formatter_agent import incident_formatter_tool
from town_hall_agents.conversation_summarizer_agent import conversation_summarizer_tool


conversation_format_coordinator_agent_instructions = """
You are a conversation format coordinator formatter agent.
You have three tools that you can use.

# Tasks in order (Strict): 
 Task 1: Your task is to check if you need to use the `feedback_formatter_tool` and the `incident_formatter_tool`. Use them if needed.
 Task 2: Summarize the conversation using the `conversation_summarizer_tool`
 Task 3: Handoff back to the dialogue agent.

1. Use the `feedback_formatter_tool` in order to structure feedback (i.e. user recommendations, )
2. Use the `incident_formatter_tool` in order to structure incidents (i.e. lost items, anomalies, violations, crime)

Special Cases:
Use both the `feedback_formatter_tool` and the `incident_formatter_tool` if the conversation contains feedback and an incident report.
"""

conversation_format_coordinator_agent = Agent(
    name = "Conversation Format Coordinator Agent",
    instructions = conversation_format_coordinator_agent_instructions,
    tools=[feedback_formatter_tool, incident_formatter_tool, conversation_summarizer_tool]
)
