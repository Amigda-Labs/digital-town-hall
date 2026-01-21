from agents import Agent
from pydantic import BaseModel


from town_hall_agents.feedback_formatter_agent import feedback_formatter_tool
from town_hall_agents.incident_formatter_agent import incident_formatter_tool

from core.models import Conversation


conversation_formatter_agent_instructions = """
You are a conversation formatter agent. Your goal is to format the conversation into a structured format.

Check first if you would be needing these tools
1. Use the `feedback_formatter_tool` in order to structure feedback (i.e. user recommendations, )
2. Use the `incident_formatter_tool` in order to structure incidents (i.e. lost items, anomalies, violations, crime)
3. Use both the `feedback_formatter_tool` and the `incident_formatter_tool` if the conversation contains feedback and an incident report.

By default: You should structure the message according to your structured output.

Example Incident Workflow:
1. Conversation -> incident_formatter_tool -> Conversation Formatter

Example Feedback Workflow:
2. Conversation -> feedback_formatter_tool -> Conversation Formatter

Example Feedback Workflow:
3. Conversation -> feedback_formatter_tool -> incident_formatter_tool -> Conversation Formatter
"""

conversation_formatter_agent = Agent(
    name = "Conversation Formatter Agent",
    instructions = conversation_formatter_agent_instructions,
    output_type = Conversation,
    tools=[feedback_formatter_tool, incident_formatter_tool]
)
